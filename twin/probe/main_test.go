package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// Fixtures independently spell out Kafka's documented non-flexible field order.
type wire struct{ bytes.Buffer }

func (w *wire) short(n int16)   { _ = binary.Write(&w.Buffer, binary.BigEndian, n) }
func (w *wire) integer(n int32) { _ = binary.Write(&w.Buffer, binary.BigEndian, n) }
func (w *wire) string(s string) { w.short(int16(len(s))); w.WriteString(s) }
func (w *wire) binary(b []byte) {
	if b == nil {
		w.integer(-1)
	} else {
		w.integer(int32(len(b)))
		w.Write(b)
	}
}

type topicPartitions struct {
	topic      string
	partitions []int32
}

func assignment(version int16, topics ...topicPartitions) []byte {
	w := &wire{}
	w.short(version)
	w.integer(int32(len(topics)))
	for _, topic := range topics {
		w.string(topic.topic)
		w.integer(int32(len(topic.partitions)))
		for _, p := range topic.partitions {
			w.integer(p)
		}
	}
	w.binary(nil)
	return w.Bytes()
}

type member struct {
	id, client, host     string
	metadata, assignment []byte
}
type description struct {
	correlation                          int32
	code                                 int16
	group, state, protocolType, protocol string
	members                              []member
}

func healthyDescription() description {
	return description{correlation: correlationID, group: "accounting", state: "Stable", protocolType: "consumer", protocol: "range",
		members: []member{{id: "member-1", client: "accounting-client", host: "/127.0.0.1", metadata: []byte("opaque-metadata-not-logged"), assignment: assignment(0, topicPartitions{"orders", []int32{0}})}}}
}
func response(value description) []byte {
	w := &wire{}
	w.integer(value.correlation)
	w.integer(1)
	w.short(value.code)
	w.string(value.group)
	w.string(value.state)
	w.string(value.protocolType)
	w.string(value.protocol)
	w.integer(int32(len(value.members)))
	for _, member := range value.members {
		w.string(member.id)
		w.string(member.client)
		w.string(member.host)
		w.binary(member.metadata)
		w.binary(member.assignment)
	}
	return w.Bytes()
}
func testContext(t *testing.T, timeout time.Duration) context.Context {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	t.Cleanup(cancel)
	return ctx
}

func TestHTTPExactEndpointAndNoResponseLogging(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		if r.Method != "GET" || r.RequestURI != "/readyz?full=1" {
			t.Errorf("unexpected request %s %s", r.Method, r.RequestURI)
		}
		io.WriteString(w, "private-response-marker")
	}))
	defer server.Close()
	var output bytes.Buffer
	if code := run([]string{"http", "--url", server.URL + "/readyz?full=1"}, &output); code != 0 {
		t.Fatalf("code %d: %s", code, output.String())
	}
	if requests.Load() != 1 || output.String() != "ready\n" {
		t.Fatalf("unexpected status: %q", output.String())
	}
}
func TestHTTPRejectsRedirectsWithoutFollowing(t *testing.T) {
	var followed atomic.Int32
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { followed.Add(1) }))
	defer target.Close()
	redirect := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, target.URL, http.StatusFound) }))
	defer redirect.Close()
	if err := checkHTTP(testContext(t, time.Second), redirect.URL); err == nil {
		t.Fatal("redirect passed readiness")
	}
	if followed.Load() != 0 {
		t.Fatal("redirect target was contacted")
	}
}
func TestHTTPStatusBodyAndTimeoutFailures(t *testing.T) {
	cases := []struct {
		name    string
		handler http.HandlerFunc
	}{
		{"204-is-not-200", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(204) }},
		{"503", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(503)
			io.WriteString(w, "private-error-body")
		}},
		{"oversized-body", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, strings.Repeat("x", maxHTTPBody+1)) }},
		{"truncated-body", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Length", "100")
			io.WriteString(w, "short")
		}},
		{"timeout", func(w http.ResponseWriter, r *http.Request) { <-r.Context().Done() }},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewServer(test.handler)
			defer server.Close()
			var output bytes.Buffer
			if code := run([]string{"http", "--url", server.URL, "--timeout", "50ms"}, &output); code == 0 {
				t.Fatal("unhealthy endpoint passed")
			}
			if strings.Contains(output.String(), "private") || strings.Contains(output.String(), server.URL) {
				t.Fatalf("unsanitized output %q", output.String())
			}
		})
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, strings.Repeat("x", maxHTTPBody)) }))
	defer server.Close()
	if err := checkHTTP(testContext(t, time.Second), server.URL); err != nil {
		t.Fatalf("exact body limit rejected: %v", err)
	}
}
func TestHTTPInvalidConfiguration(t *testing.T) {
	for _, endpoint := range []string{"", "file:///etc/passwd", "http://user:secret@localhost/", "http://localhost/#fragment", ":bad"} {
		if err := checkHTTP(testContext(t, time.Second), endpoint); err == nil {
			t.Fatalf("accepted endpoint %q", endpoint)
		}
	}
}

func TestDescribeRequiresOwnStableAssignedMember(t *testing.T) {
	local := net.ParseIP("127.0.0.1")
	for _, host := range []string{"127.0.0.1", "/127.0.0.1", "::ffff:127.0.0.1", "/[::ffff:127.0.0.1]"} {
		value := healthyDescription()
		value.members[0].host = host
		if err := parseDescribe(response(value), "accounting", "orders", local); err != nil {
			t.Fatalf("own host %s rejected: %v", host, err)
		}
	}
	cases := map[string]func(*description){
		"unstable":              func(d *description) { d.state = "PreparingRebalance" },
		"not-consumer":          func(d *description) { d.protocolType = "connect" },
		"empty-protocol":        func(d *description) { d.protocol = "" },
		"wrong-group":           func(d *description) { d.group = "fraud-detection" },
		"group-error":           func(d *description) { d.code = 16 },
		"wrong-correlation":     func(d *description) { d.correlation++ },
		"no-members":            func(d *description) { d.members = nil },
		"foreign-member":        func(d *description) { d.members[0].host = "/127.0.0.2" },
		"hostname-not-identity": func(d *description) { d.members[0].host = "localhost" },
		"empty-member":          func(d *description) { d.members[0].id = "" },
		"empty-client":          func(d *description) { d.members[0].client = "" },
		"wrong-topic":           func(d *description) { d.members[0].assignment = assignment(0, topicPartitions{"other", []int32{0}}) },
		"empty-partitions":      func(d *description) { d.members[0].assignment = assignment(0, topicPartitions{"orders", nil}) },
		"empty-assignment":      func(d *description) { d.members[0].assignment = []byte{} },
		"null-metadata":         func(d *description) { d.members[0].metadata = nil },
		"null-assignment":       func(d *description) { d.members[0].assignment = nil },
		"oversized-name":        func(d *description) { d.members[0].id = strings.Repeat("a", maxStringBytes+1) },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			value := healthyDescription()
			mutate(&value)
			if err := parseDescribe(response(value), "accounting", "orders", local); err == nil {
				t.Fatal("unready group accepted")
			}
		})
	}
	value := healthyDescription()
	foreign := value.members[0]
	foreign.host = "/127.0.0.2"
	value.members = append([]member{foreign}, value.members...)
	if err := parseDescribe(response(value), "accounting", "orders", local); err != nil {
		t.Fatal(err)
	}
}
func TestAssignmentsVersionsBoundsAndOpaqueUserData(t *testing.T) {
	for version := int16(0); version <= 3; version++ {
		data := assignment(version, topicPartitions{"orders", []int32{0, 1}}, topicPartitions{"other", []int32{3}})
		if found, err := parseAssignment(data, "orders"); err != nil || !found {
			t.Fatalf("version %d: %v", version, err)
		}
	}
	invalid := [][]byte{
		assignment(-1, topicPartitions{"orders", []int32{0}}), assignment(4, topicPartitions{"orders", []int32{0}}),
		assignment(0, topicPartitions{"orders", []int32{-1}}), assignment(0, topicPartitions{"orders", []int32{1, 1}}),
		assignment(0, topicPartitions{"orders", []int32{1}}, topicPartitions{"orders", []int32{2}}), assignment(0, topicPartitions{"", []int32{1}}),
	}
	for i, data := range invalid {
		if _, err := parseAssignment(data, "orders"); err == nil {
			t.Fatalf("invalid assignment %d accepted", i)
		}
	}
	valid := assignment(0, topicPartitions{"orders", []int32{0}})
	for i := 0; i < len(valid); i++ {
		if _, err := parseAssignment(valid[:i], "orders"); err == nil {
			t.Fatalf("truncation %d accepted", i)
		}
	}
	for _, count := range []uint32{0xffffffff, maxTopics + 1, 0x7fffffff} {
		bad := append([]byte(nil), valid...)
		binary.BigEndian.PutUint32(bad[2:6], count)
		if _, err := parseAssignment(bad, "orders"); err == nil {
			t.Fatalf("topic count %d accepted", count)
		}
	}
	w := &wire{}
	w.Write(valid[:len(valid)-4])
	w.binary([]byte("opaque-user-data-must-not-be-interpreted"))
	if found, err := parseAssignment(w.Bytes(), "orders"); err != nil || !found {
		t.Fatal("opaque metadata interfered with readiness", err)
	}
	if _, err := parseAssignment(append(valid, 0), "orders"); err == nil {
		t.Fatal("trailing assignment data accepted")
	}
}
func TestDescribeTruncationAndCountsFailClosed(t *testing.T) {
	valid := response(healthyDescription())
	for n := 0; n < len(valid); n++ {
		if err := parseDescribe(valid[:n], "accounting", "orders", net.ParseIP("127.0.0.1")); err == nil {
			t.Fatalf("truncation %d passed", n)
		}
	}
	for _, count := range []uint32{0, 2, 0xffffffff, 0x7fffffff} {
		bad := append([]byte(nil), valid...)
		binary.BigEndian.PutUint32(bad[4:8], count)
		if err := parseDescribe(bad, "accounting", "orders", net.ParseIP("127.0.0.1")); err == nil {
			t.Fatalf("group count %d passed", count)
		}
	}
	if err := parseDescribe(append(valid, 1), "accounting", "orders", net.ParseIP("127.0.0.1")); err == nil {
		t.Fatal("trailing response accepted")
	}
}

// Captures the one read-only request and supplies controlled protocol bytes.
func brokerServer(t *testing.T, answer func(net.Conn, []byte)) string {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	go func() {
		defer close(done)
		connection, err := listener.Accept()
		if err != nil {
			return
		}
		defer connection.Close()
		_ = connection.SetDeadline(time.Now().Add(2 * time.Second))
		var prefix [4]byte
		if _, err := io.ReadFull(connection, prefix[:]); err != nil {
			t.Error(err)
			return
		}
		n := int32(binary.BigEndian.Uint32(prefix[:]))
		if n < 8 || n > 4096 {
			t.Error("bad request frame")
			return
		}
		request := make([]byte, int(n))
		if _, err := io.ReadFull(connection, request); err != nil {
			t.Error(err)
			return
		}
		answer(connection, request)
	}()
	t.Cleanup(func() {
		listener.Close()
		select {
		case <-done:
		case <-time.After(3 * time.Second):
			t.Error("broker goroutine did not exit")
		}
	})
	return listener.Addr().String()
}
func TestKafkaWireReadinessUsesOnlyDescribeGroupsAndHandlesFragmentedIO(t *testing.T) {
	broker := brokerServer(t, func(connection net.Conn, request []byte) {
		want := &wire{}
		want.short(15)
		want.short(0)
		want.integer(correlationID)
		want.string("lineage-healthcheck")
		want.integer(1)
		want.string("accounting")
		if !bytes.Equal(request, want.Bytes()) {
			t.Errorf("not a single DescribeGroups v0 request: %x", request)
		}
		body := response(healthyDescription())
		framed := &wire{}
		framed.integer(int32(len(body)))
		framed.Write(body)
		for _, value := range framed.Bytes() {
			if _, err := connection.Write([]byte{value}); err != nil {
				t.Error(err)
				return
			}
		}
		var extra [1]byte
		if n, err := connection.Read(extra[:]); n != 0 || err != io.EOF {
			t.Errorf("unexpected additional request: n=%d err=%v", n, err)
		}
	})
	var output bytes.Buffer
	if code := run([]string{"kafka", "--broker", broker, "--group", "accounting", "--topic", "orders"}, &output); code != 0 {
		t.Fatalf("code %d: %s", code, output.String())
	}
	if output.String() != "ready\n" {
		t.Fatalf("unexpected output %q", output.String())
	}
}
func TestKafkaFrameAndDeadlineFailuresAreSanitized(t *testing.T) {
	cases := map[string]func(net.Conn){
		"oversized":        func(c net.Conn) { _ = binary.Write(c, binary.BigEndian, int32(maxFrameSize+1)) },
		"negative":         func(c net.Conn) { _ = binary.Write(c, binary.BigEndian, int32(-1)) },
		"empty":            func(c net.Conn) { _ = binary.Write(c, binary.BigEndian, int32(0)) },
		"truncated-prefix": func(c net.Conn) { c.Write([]byte{0, 0}) },
		"truncated-body": func(c net.Conn) {
			_ = binary.Write(c, binary.BigEndian, int32(100))
			c.Write([]byte("private-response-marker"))
		},
		"deadline": func(c net.Conn) { var extra [1]byte; c.Read(extra[:]) },
	}
	for name, write := range cases {
		t.Run(name, func(t *testing.T) {
			broker := brokerServer(t, func(c net.Conn, request []byte) { write(c) })
			var output bytes.Buffer
			start := time.Now()
			if code := run([]string{"kafka", "--broker", broker, "--group", "accounting", "--topic", "orders", "--timeout", "50ms"}, &output); code == 0 {
				t.Fatal("bad frame passed")
			}
			if time.Since(start) > time.Second {
				t.Fatal("deadline was not enforced")
			}
			if strings.Contains(output.String(), "private") || strings.Contains(output.String(), broker) {
				t.Fatalf("unsanitized output %q", output.String())
			}
		})
	}
}
func TestCLIRejectsInvalidArgumentsWithoutEchoingThem(t *testing.T) {
	for _, args := range [][]string{nil, {"secret-mode"}, {"http", "--secret-token", "private"}, {"http", "--timeout", "0s"}, {"kafka", "--timeout", "31s"}, {"http", "extra"}} {
		var output bytes.Buffer
		if code := run(args, &output); code != 2 || output.String() != "not ready: invalid-arguments\n" {
			t.Fatalf("unexpected CLI result %d: %q", code, output.String())
		}
	}
	for _, pair := range [][3]string{{"", "accounting", "orders"}, {"localhost", "accounting", "orders"}, {"127.0.0.1:1", "", "orders"}, {"127.0.0.1:1", "accounting", ""}} {
		if err := checkKafka(testContext(t, time.Second), pair[0], pair[1], pair[2]); err == nil {
			t.Fatalf("invalid config accepted: %v", pair)
		}
	}
}
func FuzzDescribeNeverPanics(f *testing.F) {
	f.Add(response(healthyDescription()))
	f.Add([]byte{0xff, 0xff})
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > maxFrameSize {
			t.Skip()
		}
		_ = parseDescribe(data, "accounting", "orders", net.ParseIP("127.0.0.1"))
	})
}
func FuzzAssignmentNeverPanics(f *testing.F) {
	f.Add(assignment(0, topicPartitions{"orders", []int32{0}}))
	f.Add([]byte{0xff, 0xff})
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > maxFrameSize {
			t.Skip()
		}
		_, _ = parseAssignment(data, "orders")
	})
}
