

def format_timestamp_ms(ms):
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}hr {m}m {s}s {ms}ms"
    else:
        return f"{m}m {s}s {ms}ms"
