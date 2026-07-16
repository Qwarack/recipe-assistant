def split_text(
    lines: list[str],
    *,
    max_length: int = 1024,
) -> list[str]:
    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in lines:
        extra_length = len(line)

        if current_lines:
            extra_length += 1

        if current_lines and current_length + extra_length > max_length:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_length = 0

        if len(line) > max_length:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_length = 0

            for start in range(0, len(line), max_length):
                chunks.append(line[start : start + max_length])

            continue

        current_lines.append(line)
        current_length += extra_length

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks
