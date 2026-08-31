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
            Ok(mut response) => response
                .body_mut()
                .read_json::<Value>()
                .map_err(|error| HarnessError::Decode(error.to_string())),
            Err(ureq::Error::StatusCode(code)) => Err(HarnessError::Status {
                code,
                body: String::new(),
            }),
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
    // ureq surfaces the status without headers on the error path; exponential
    // backoff covers the case. Kept as a seam so a header-aware transport can
    // honour `retry-after` without touching the retry loop.
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
