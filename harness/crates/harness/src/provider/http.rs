use std::thread::sleep;
use std::time::Duration;

use serde_json::Value;

use crate::error::HarnessError;

/// Retry policy for one endpoint. Deliberately explicit rather than inherited
/// from an SDK: a formalization run is long and expensive, and silently giving
/// up on a 429 halfway through is worse than waiting.
#[derive(Debug, Clone)]
pub struct RetryPolicy {
    pub max_attempts: u32,
    pub base_delay: Duration,
    pub max_delay: Duration,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self {
            max_attempts: 5,
            base_delay: Duration::from_secs(1),
            max_delay: Duration::from_secs(60),
        }
    }
}

impl RetryPolicy {
    fn backoff(&self, attempt: u32, retry_after: Option<Duration>) -> Duration {
        if let Some(delay) = retry_after {
            return delay.min(self.max_delay);
        }
        let factor = 1u64 << attempt.min(16);
        self.base_delay
            .saturating_mul(factor as u32)
            .min(self.max_delay)
    }
}

/// A JSON-over-HTTPS transport with retries. The only network code in the
/// workspace.
pub struct JsonHttp {
    agent: ureq::Agent,
    pub retry: RetryPolicy,
}

impl JsonHttp {
    pub fn new(timeout: Duration) -> Self {
        let config = ureq::Agent::config_builder()
            .timeout_global(Some(timeout))
            // Do not let the transport turn a non-2xx into an opaque error: the
            // provider explains *why* a request was rejected in the response
            // body, and losing it leaves "HTTP 400" with nothing to act on.
            .http_status_as_error(false)
            .build();
        Self {
            agent: config.new_agent(),
            retry: RetryPolicy::default(),
        }
    }

    /// POST `body` and decode the JSON response, retrying transport failures,
    /// 408, 409, 429 and 5xx. 4xx responses other than those are returned
    /// immediately — retrying a malformed request only wastes the budget.
    pub fn post_json(
        &self,
        url: &str,
        headers: &[(&str, String)],
        body: &Value,
    ) -> Result<Value, HarnessError> {
        let mut last: HarnessError = HarnessError::Transport("no attempt was made".into());
        for attempt in 0..self.retry.max_attempts {
            if attempt > 0 {
                let delay = self.retry.backoff(attempt - 1, retry_after(&last));
                sleep(delay);
            }
            match self.attempt(url, headers, body) {
                Ok(value) => return Ok(value),
                Err(error) if is_retryable(&error) => last = error,
                Err(error) => return Err(error),
            }
        }
        Err(last)
    }

    fn attempt(
        &self,
        url: &str,
        headers: &[(&str, String)],
        body: &Value,
    ) -> Result<Value, HarnessError> {
        let mut request = self.agent.post(url);
        for (name, value) in headers {
            request = request.header(*name, value.as_str());
        }
        match request.send_json(body) {
            Ok(mut response) => {
                let status = response.status().as_u16();
                if (200..300).contains(&status) {
                    // Read, then parse, so the two failures stay distinct: a
                    // connection dropped mid-body is transient and worth
                    // retrying, while a fully received body that will not parse
                    // is not going to parse on the next attempt either.
                    let text = response
                        .body_mut()
                        .read_to_string()
                        .map_err(|error| HarnessError::Transport(format!(
                            "the response body ended early: {error}"
                        )))?;
                    return serde_json::from_str::<Value>(&text).map_err(|error| {
                        HarnessError::Decode(format!(
                            "{error}; body was {}",
                            crate::error::truncate(&text, 500)
                        ))
                    });
                }
                // Carry the provider's explanation through, truncated: it names
                // the offending field on a 400 and the reset time on a 429.
                let body = response
                    .body_mut()
                    .read_to_string()
                    .unwrap_or_else(|error| format!("<unreadable body: {error}>"));
                Err(HarnessError::Status {
                    code: status,
                    body: crate::error::truncate(&body, 2000),
                })
            }
            Err(error) => Err(HarnessError::Transport(error.to_string())),
        }
    }
}

fn is_retryable(error: &HarnessError) -> bool {
    match error {
        HarnessError::Transport(_) => true,
        HarnessError::Status { code, .. } => {
            matches!(code, 408 | 409 | 429) || *code >= 500
        }
        _ => false,
    }
}

fn retry_after(_error: &HarnessError) -> Option<Duration> {
    // Seam for honouring a `retry-after` header. The status path now keeps the
    // body but not the headers, so exponential backoff still covers 429.
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn retries_only_transient_failures() {
        assert!(is_retryable(&HarnessError::Transport("reset".into())));
        for code in [408, 409, 429, 500, 503] {
            assert!(is_retryable(&HarnessError::Status {
                code,
                body: String::new()
            }));
        }
        for code in [400, 401, 403, 404, 422] {
            assert!(!is_retryable(&HarnessError::Status {
                code,
                body: String::new()
            }));
        }
        assert!(!is_retryable(&HarnessError::Decode("bad".into())));
    }

    #[test]
    fn backoff_grows_and_is_capped() {
        let policy = RetryPolicy::default();
        assert_eq!(policy.backoff(0, None), Duration::from_secs(1));
        assert_eq!(policy.backoff(1, None), Duration::from_secs(2));
        assert_eq!(policy.backoff(3, None), Duration::from_secs(8));
        assert_eq!(policy.backoff(30, None), policy.max_delay);
    }
}

#[cfg(test)]
mod status_tests {
    use super::*;
    use std::io::{BufRead, BufReader, Write};
    use std::net::TcpListener;

    /// One-shot HTTP server that answers with the given status and body.
    fn serve_once(status: u16, body: &'static str) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
        let port = listener.local_addr().expect("addr").port();
        std::thread::spawn(move || {
            let Ok((stream, _)) = listener.accept() else {
                return;
            };
            let mut reader = BufReader::new(&stream);
            // Drain headers, then the declared body, so the client sees a
            // complete request rather than a reset connection.
            let mut length = 0usize;
            loop {
                let mut line = String::new();
                if reader.read_line(&mut line).unwrap_or(0) == 0 || line == "\r\n" {
                    break;
                }
                if let Some(value) = line.to_lowercase().strip_prefix("content-length:") {
                    length = value.trim().parse().unwrap_or(0);
                }
            }
            let mut discard = vec![0u8; length];
            use std::io::Read;
            let _ = reader.read_exact(&mut discard);
            let mut stream = &stream;
            let _ = write!(
                stream,
                "HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            let _ = stream.flush();
        });
        format!("http://127.0.0.1:{port}/")
    }

    #[test]
    fn a_rejected_request_keeps_the_providers_explanation() {
        let url = serve_once(
            400,
            r#"{"type":"error","error":{"type":"invalid_request_error","message":"tools.0.name: unsupported"}}"#,
        );
        let http = JsonHttp::new(Duration::from_secs(5));
        let error = http
            .post_json(&url, &[], &serde_json::json!({"hello": "world"}))
            .expect_err("400 must be an error");

        match error {
            HarnessError::Status { code, body } => {
                assert_eq!(code, 400);
                // Without this, the operator sees "HTTP 400" and nothing else.
                assert!(body.contains("tools.0.name: unsupported"), "{body}");
            }
            other => panic!("expected a status error, got {other:?}"),
        }
    }

    #[test]
    fn a_successful_response_still_decodes() {
        let url = serve_once(200, r#"{"stop_reason":"end_turn"}"#);
        let http = JsonHttp::new(Duration::from_secs(5));
        let value = http
            .post_json(&url, &[], &serde_json::json!({}))
            .expect("200 decodes");
        assert_eq!(value["stop_reason"], serde_json::json!("end_turn"));
    }
}

#[cfg(test)]
mod auth_tests {
    use super::super::anthropic::{AnthropicConfig, AnthropicProvider, Credential};
    use super::super::{Provider, Request};
    use std::io::{BufRead, BufReader, Read, Write};
    use std::net::TcpListener;
    use std::sync::mpsc;
    use std::time::Duration;

    /// A server that records the request headers it was sent, then answers with
    /// a minimal valid turn.
    #[test]
    fn an_oauth_token_reaches_the_api_as_a_bearer_credential() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
        let port = listener.local_addr().unwrap().port();
        let (sender, receiver) = mpsc::channel::<String>();
        std::thread::spawn(move || {
            let Ok((stream, _)) = listener.accept() else {
                return;
            };
            let mut reader = BufReader::new(&stream);
            let mut headers = String::new();
            let mut length = 0usize;
            loop {
                let mut line = String::new();
                if reader.read_line(&mut line).unwrap_or(0) == 0 || line == "\r\n" {
                    break;
                }
                if let Some(value) = line.to_lowercase().strip_prefix("content-length:") {
                    length = value.trim().parse().unwrap_or(0);
                }
                headers.push_str(&line.to_lowercase());
            }
            let mut discard = vec![0u8; length];
            let _ = reader.read_exact(&mut discard);
            let body = r#"{"model":"claude-opus-5","stop_reason":"end_turn","content":[{"type":"text","text":"ok"}],"usage":{"input_tokens":1,"output_tokens":1}}"#;
            let mut stream = &stream;
            let _ = write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            let _ = stream.flush();
            let _ = sender.send(headers);
        });

        let provider = AnthropicProvider::new(AnthropicConfig {
            credential: Credential::OAuth("sk-ant-oat01-secret".into()),
            base_url: format!("http://127.0.0.1:{port}"),
            model: "claude-opus-5".into(),
            max_tokens: 16,
            effort: None,
            strict_tools: false,
            timeout: Duration::from_secs(5),
        });
        let turn = provider
            .turn(&Request {
            prompt_pending: true,
            session: 1,
                system: "s",
                prompt: "p",
                exchanges: &[],
                tools: &[],
            })
            .expect("the turn completes");
        assert_eq!(turn.text, "ok");

        let headers = receiver
            .recv_timeout(Duration::from_secs(5))
            .expect("the server saw a request");
        assert!(
            headers.contains("authorization: bearer sk-ant-oat01-secret"),
            "{headers}"
        );
        // Without this beta the Messages API does not accept an OAuth token.
        assert!(headers.contains("anthropic-beta: oauth-2025-04-20"), "{headers}");
        assert!(!headers.contains("x-api-key"), "{headers}");
    }
}
