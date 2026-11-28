// lineage-healthcheck performs read-only, metadata-only readiness checks.
package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
	"unicode/utf8"
)

const (
	defaultTimeout       = 5 * time.Second
	maxTimeout           = 30 * time.Second
	maxHTTPBody          = 16 << 10
	maxFrameSize         = 1 << 20
	maxStringBytes       = 4096
	maxMembers           = 1024
	maxTopics            = 1024
	maxPartitions        = 65536
	correlationID  int32 = 0x4c484301
)

var errMalformed = errors.New("kafka-malformed-response")

func main() { os.Exit(run(os.Args[1:], os.Stderr)) }

func run(args []string, output io.Writer) int {
	if len(args) == 0 {
		return report(output, "invalid-arguments", 2)
	}
	flags := flag.NewFlagSet("lineage-healthcheck", flag.ContinueOnError)
	flags.SetOutput(io.Discard) // Never echo user-supplied URLs, arguments or responses.
	timeout := flags.Duration("timeout", defaultTimeout, "total readiness deadline")
	var endpoint, broker, group, topic *string
	switch args[0] {
	case "http":
		endpoint = flags.String("url", "", "exact HTTP readiness endpoint")
	case "kafka":
		broker = flags.String("broker", "", "single-broker host:port")
		group = flags.String("group", "", "consumer group")
		topic = flags.String("topic", "", "expected assigned topic")
	default:
		return report(output, "invalid-arguments", 2)
	}
	if flags.Parse(args[1:]) != nil || flags.NArg() != 0 || *timeout <= 0 || *timeout > maxTimeout {
		return report(output, "invalid-arguments", 2)
	}
	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()
	var err error
	if endpoint != nil {
		err = checkHTTP(ctx, *endpoint)
	} else {
		err = checkKafka(ctx, *broker, *group, *topic)
	}
	if err != nil {
		return report(output, err.Error(), 1)
	}
	fmt.Fprintln(output, "ready")
	return 0
}

func report(output io.Writer, category string, code int) int {
	fmt.Fprintln(output, "not ready: "+category)
	return code
}

func checkHTTP(ctx context.Context, endpoint string) error {
	u, err := url.Parse(endpoint)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" || u.User != nil || u.Fragment != "" {
		return errors.New("http-invalid-endpoint")
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return errors.New("http-invalid-endpoint")
	}
	transport := &http.Transport{Proxy: nil, DisableKeepAlives: true, DisableCompression: true,
		MaxResponseHeaderBytes: 16 << 10}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: maxTimeout,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	response, err := client.Do(request)
	if err != nil {
		return errors.New("http-unavailable")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return errors.New("http-not-200")
	}
	n, err := io.Copy(io.Discard, io.LimitReader(response.Body, maxHTTPBody+1))
	if err != nil {
		return errors.New("http-incomplete-body")
	}
	if n > maxHTTPBody {
		return errors.New("http-body-limit")
	}
	return nil
}

// decoder has a sticky error and never allocates according to untrusted counts.
type decoder struct {
	data   []byte
	offset int
	err    error
}

func (d *decoder) take(n int) []byte {
	if d.err != nil {
		return nil
	}
	if n < 0 || n > len(d.data)-d.offset {
		d.err = errMalformed
		return nil
	}
	result := d.data[d.offset : d.offset+n]
	d.offset += n
	return result
}
func (d *decoder) i16() int16 {
	value := d.take(2)
	if value == nil {
		return 0
	}
	return int16(binary.BigEndian.Uint16(value))
}
func (d *decoder) i32() int32 {
	value := d.take(4)
	if value == nil {
		return 0
	}
	return int32(binary.BigEndian.Uint32(value))
}
func (d *decoder) text() string {
	n := int(d.i16())
	if n < 0 || n > maxStringBytes {
		d.err = errMalformed
		return ""
	}
	value := d.take(n)
	if !utf8.Valid(value) {
		d.err = errMalformed
		return ""
	}
	return string(value)
}
func (d *decoder) blob(nullable bool) []byte {
	n := d.i32()
	if nullable && n == -1 {
		return nil
	}
	if n < 0 || n > maxFrameSize {
		d.err = errMalformed
		return nil
	}
	return d.take(int(n))
}
func (d *decoder) count(limit, minimumBytes int) int {
	n := d.i32()
	if d.err != nil {
		return 0
	}
	if n < 0 || n > int32(limit) || (minimumBytes > 0 && int(n) > (len(d.data)-d.offset)/minimumBytes) {
		d.err = errMalformed
		return 0
	}
	return int(n)
}
func (d *decoder) finish() error {
	if d.err != nil || d.offset != len(d.data) {
		return errMalformed
	}
	return nil
}

func put16(buffer *bytes.Buffer, value int16) { _ = binary.Write(buffer, binary.BigEndian, value) }
func put32(buffer *bytes.Buffer, value int32) { _ = binary.Write(buffer, binary.BigEndian, value) }
func putText(buffer *bytes.Buffer, value string) {
	put16(buffer, int16(len(value)))
	buffer.WriteString(value)
}

func describeRequest(group string) []byte {
	var body bytes.Buffer
	put16(&body, 15) // DescribeGroups, no Fetch, JoinGroup, Heartbeat or offsets.
	put16(&body, 0)  // Non-flexible v0: no throttle time or tagged fields.
	put32(&body, correlationID)
	putText(&body, "lineage-healthcheck")
	put32(&body, 1)
	putText(&body, group)
	var frame bytes.Buffer
	put32(&frame, int32(body.Len()))
	frame.Write(body.Bytes())
	return frame.Bytes()
}

func checkKafka(ctx context.Context, broker, group, topic string) error {
	if !validName(group) || !validName(topic) {
		return errors.New("kafka-invalid-arguments")
	}
	host, port, err := net.SplitHostPort(broker)
	if err != nil || host == "" || port == "" {
		return errors.New("kafka-invalid-broker")
	}
	connection, err := (&net.Dialer{Timeout: defaultTimeout}).DialContext(ctx, "tcp", broker)
	if err != nil {
		return errors.New("kafka-unavailable")
	}
	defer connection.Close()
	local, ok := connection.LocalAddr().(*net.TCPAddr)
	if !ok || local.IP == nil {
		return errors.New("kafka-local-address")
	}
	deadline, bounded := ctx.Deadline()
	if !bounded {
		deadline = time.Now().Add(defaultTimeout)
	}
	if err := connection.SetDeadline(deadline); err != nil {
		return errors.New("kafka-deadline")
	}
	if _, err := io.Copy(connection, bytes.NewReader(describeRequest(group))); err != nil {
		return errors.New("kafka-write-failed")
	}
	var prefix [4]byte
	if _, err := io.ReadFull(connection, prefix[:]); err != nil {
		return errors.New("kafka-incomplete-frame")
	}
	size := int32(binary.BigEndian.Uint32(prefix[:]))
	if size < 8 || size > maxFrameSize {
		return errors.New("kafka-frame-limit")
	}
	response := make([]byte, int(size))
	if _, err := io.ReadFull(connection, response); err != nil {
		return errors.New("kafka-incomplete-frame")
	}
	return parseDescribe(response, group, topic, local.IP)
}

func validName(value string) bool {
	if len(value) == 0 || len(value) > 255 {
		return false
	}
	for _, char := range value {
		if char < 33 || char > 126 {
			return false
		}
	}
	return true
}

func sameHost(host string, local net.IP) bool {
	host = strings.TrimPrefix(host, "/")
	if strings.HasPrefix(host, "[") && strings.HasSuffix(host, "]") {
		host = host[1 : len(host)-1]
	}
	parsed := net.ParseIP(host)
	return parsed != nil && parsed.Equal(local)
}

func parseDescribe(response []byte, group, topic string, local net.IP) error {
	d := decoder{data: response}
	if d.i32() != correlationID {
		return errors.New("kafka-correlation-mismatch")
	}
	if d.count(1, 14) != 1 {
		return errMalformed
	}
	code := d.i16()
	actualGroup, state, protocolType, protocol := d.text(), d.text(), d.text(), d.text()
	members := d.count(maxMembers, 14)
	selfAssigned := false
	for i := 0; i < members; i++ {
		memberID, clientID, host := d.text(), d.text(), d.text()
		d.blob(false) // Consumer subscription metadata: never inspect or log it.
		assignment := d.blob(false)
		if d.err != nil {
			return errMalformed
		}
		assigned, err := parseAssignment(assignment, topic)
		if err != nil {
			return err
		}
		if memberID != "" && clientID != "" && sameHost(host, local) && assigned {
			selfAssigned = true
		}
	}
	if err := d.finish(); err != nil {
		return err
	}
	if code != 0 {
		return errors.New("kafka-group-unavailable")
	}
	if actualGroup != group {
		return errors.New("kafka-group-mismatch")
	}
	if state != "Stable" || protocolType != "consumer" || protocol == "" {
		return errors.New("kafka-group-not-stable-consumer")
	}
	if !selfAssigned {
		return errors.New("kafka-local-member-not-assigned")
	}
	return nil
}

func parseAssignment(data []byte, expectedTopic string) (bool, error) {
	d := decoder{data: data}
	version := d.i16()
	if version < 0 || version > 3 {
		return false, errors.New("kafka-assignment-version")
	}
	count := d.count(maxTopics, 6)
	found := false
	topics := make(map[string]bool)
	for i := 0; i < count; i++ {
		topic := d.text()
		if topic == "" || topics[topic] {
			return false, errMalformed
		}
		topics[topic] = true
		partitions := d.count(maxPartitions, 4)
		seen := make(map[int32]bool)
		for j := 0; j < partitions; j++ {
			partition := d.i32()
			if d.err != nil || partition < 0 || seen[partition] {
				return false, errMalformed
			}
			seen[partition] = true
		}
		if topic == expectedTopic && partitions > 0 {
			found = true
		}
	}
	d.blob(true) // Opaque assignment user data is skipped, never interpreted.
	if err := d.finish(); err != nil {
		return false, err
	}
	return found, nil
}
