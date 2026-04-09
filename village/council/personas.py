"""Council personas -- load and manage deliberation personas."""

from dataclasses import dataclass, field
from pathlib import Path

from village.memory import _format_frontmatter, _parse_frontmatter


@dataclass
class Persona:
    name: str
    model: str = "anthropic/claude-3.5-sonnet"
    temperature: float = 0.7
    tags: list[str] = field(default_factory=list)
    system_prompt: str = ""

    def to_markdown(self) -> str:
        meta: dict[str, str | list[str]] = {
            "name": self.name,
            "model": self.model,
            "temperature": str(self.temperature),
            "tags": self.tags,
        }
        lines = ["---"]
        lines.append(_format_frontmatter(meta))
        lines.append("---")
        lines.append("")
        lines.append(self.system_prompt)
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, content: str) -> "Persona":
        meta, body = _parse_frontmatter(content)
        name = str(meta.get("name", "unknown"))
        model = str(meta.get("model", "anthropic/claude-3.5-sonnet"))
        temp_str = str(meta.get("temperature", "0.7"))
        try:
            temperature = float(temp_str)
        except ValueError:
            temperature = 0.7
        tags_raw = meta.get("tags", [])
        tags = tags_raw if isinstance(tags_raw, list) else [str(tags_raw)]
        return cls(
            name=name,
            model=model,
            temperature=temperature,
            tags=tags,
            system_prompt=body,
        )


class PersonaLoader:
    def __init__(self, personas_dir: Path | None = None) -> None:
        if personas_dir is None:
            personas_dir = Path.cwd() / "personas"
        self.personas_dir = personas_dir

    def load(self, name: str) -> Persona:
        path = self.personas_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Persona not found: {name}")
        content = path.read_text(encoding="utf-8")
        return Persona.from_markdown(content)

    def load_all(self) -> list[Persona]:
        if not self.personas_dir.exists():
            return []
        personas: list[Persona] = []
        for md_file in sorted(self.personas_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                personas.append(Persona.from_markdown(content))
            except Exception:
                continue
        return personas

    def create_persona(self, name: str, description: str) -> Persona:
        path = self.personas_dir / f"{name}.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            return Persona.from_markdown(content)

        self.personas_dir.mkdir(parents=True, exist_ok=True)
        system_prompt = (
            description if description else f"You are {name}, a thoughtful participant in group deliberations."
        )
        persona = Persona(
            name=name,
            system_prompt=system_prompt,
        )
        path.write_text(persona.to_markdown(), encoding="utf-8")
        return persona
