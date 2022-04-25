import re
import typing as t

PLACEHOLDERS_REGEX = r"\{(.*?)\}"
PLACEHOLDERS_PATTERN = re.compile(PLACEHOLDERS_REGEX)


def substitute_placeholder_tokens(
    subject: str,
) -> t.Tuple[str, t.List[t.Tuple[int, str]]]:
    placeholder_tokens: t.List[t.Tuple[int, str]] = []
    sanitized_subject = str(subject)
    tokens = subject.split(".")
    for match in list(PLACEHOLDERS_PATTERN.finditer(subject)):
        start = match.start()
        end = match.end()
        placeholder = subject[start : end - 1] + "}"
        # Replace in sanitized subject
        sanitized_subject = sanitized_subject.replace(placeholder, "*")
        # Get placeholder name
        placeholder_name = placeholder[1:-1]
        # Check that placeholder is indeed a whole token and not just a part
        try:
            next_char = subject[end]
        except IndexError:
            next_char = ""
        if start:
            previous_char = subject[start - 1]
        else:
            previous_char = ""
        if previous_char and previous_char != ".":
            raise ValueError("Placeholder must occupy whole token")
        if next_char and next_char != ".":
            raise ValueError("Placeholder must occupy whole token")
        # Append placeholder
        placeholder_tokens.append(
            (
                tokens.index(placeholder),
                placeholder_name,
            )
        )

    return sanitized_subject, placeholder_tokens
