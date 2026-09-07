use std::time::{SystemTime, UNIX_EPOCH};

/// UTC timestamp in the exact shape the Python pipeline writes, so Rust-produced
/// and Python-produced artifacts stay diffable: `2026-08-31T21:57:03.123456Z`.
pub fn utc_now_iso() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    iso_from_unix_micros(now.as_micros() as i64)
}

/// Split a microsecond epoch into a civil date-time. Uses Howard Hinnant's
/// `civil_from_days`, which is exact for the whole proleptic Gregorian range.
pub fn iso_from_unix_micros(micros: i64) -> String {
    let (seconds, micros_part) = (micros.div_euclid(1_000_000), micros.rem_euclid(1_000_000));
    let days = seconds.div_euclid(86_400);
    let secs_of_day = seconds.rem_euclid(86_400);
    let (year, month, day) = civil_from_days(days);
    let (hour, minute, second) = (
        secs_of_day / 3600,
        (secs_of_day % 3600) / 60,
        secs_of_day % 60,
    );
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{micros_part:06}Z")
}

fn civil_from_days(days: i64) -> (i64, u32, u32) {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m as u32, d as u32)
}

#[cfg(test)]
mod tests {
    use super::iso_from_unix_micros;

    #[test]
    fn formats_known_instants() {
        assert_eq!(iso_from_unix_micros(0), "1970-01-01T00:00:00.000000Z");
        // 2026-08-31T21:57:03.123456Z
        assert_eq!(
            iso_from_unix_micros(1_788_213_423_123_456),
            "2026-08-31T21:57:03.123456Z"
        );
        // Leap day, and a pre-epoch instant (negative micros must not skew).
        assert_eq!(
            iso_from_unix_micros(1_709_164_800_000_000),
            "2024-02-29T00:00:00.000000Z"
        );
        assert_eq!(iso_from_unix_micros(-1), "1969-12-31T23:59:59.999999Z");
    }
}
