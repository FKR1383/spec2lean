export type DuplicateJsonKey = {
  path: string
  key: string
}

class JsonKeyScanner {
  private index = 0
  readonly duplicates: DuplicateJsonKey[] = []

  constructor(private readonly source: string) {}

  scan(): DuplicateJsonKey[] {
    this.skipWhitespace()
    this.value("$")
    this.skipWhitespace()
    return this.duplicates
  }

  private skipWhitespace(): void {
    while (/\s/.test(this.source[this.index] ?? "")) this.index += 1
  }

  private value(path: string): void {
    this.skipWhitespace()
    const current = this.source[this.index]
    if (current === "{") this.object(path)
    else if (current === "[") this.array(path)
    else if (current === '"') this.string()
    else this.primitive()
  }

  private object(path: string): void {
    this.index += 1
    this.skipWhitespace()
    const keys = new Set<string>()
    if (this.source[this.index] === "}") {
      this.index += 1
      return
    }
    while (this.index < this.source.length) {
      this.skipWhitespace()
      const key = this.string()
      if (keys.has(key)) this.duplicates.push({ path, key })
      keys.add(key)
      this.skipWhitespace()
      if (this.source[this.index] === ":") this.index += 1
      this.value(jsonChildPath(path, key))
      this.skipWhitespace()
      if (this.source[this.index] === "}") {
        this.index += 1
        return
      }
      if (this.source[this.index] === ",") this.index += 1
    }
  }

  private array(path: string): void {
    this.index += 1
    this.skipWhitespace()
    if (this.source[this.index] === "]") {
      this.index += 1
      return
    }
    let item = 0
    while (this.index < this.source.length) {
      this.value(`${path}[${item}]`)
      item += 1
      this.skipWhitespace()
      if (this.source[this.index] === "]") {
        this.index += 1
        return
      }
      if (this.source[this.index] === ",") this.index += 1
    }
  }

  private string(): string {
    const start = this.index
    this.index += 1
    let escaped = false
    while (this.index < this.source.length) {
      const current = this.source[this.index]!
      this.index += 1
      if (escaped) {
        escaped = false
        continue
      }
      if (current === "\\") {
        escaped = true
        continue
      }
      if (current === '"') break
    }
    return JSON.parse(this.source.slice(start, this.index)) as string
  }

  private primitive(): void {
    while (
      this.index < this.source.length &&
      !/[\s,\]}]/.test(this.source[this.index]!)
    ) this.index += 1
  }
}

function jsonChildPath(parent: string, key: string): string {
  return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)
    ? `${parent}.${key}`
    : `${parent}[${JSON.stringify(key)}]`
}

/** JSON.parse accepts duplicate object keys by silently keeping the last one. */
export function duplicateJsonKeys(source: string): DuplicateJsonKey[] {
  try {
    JSON.parse(source)
    return new JsonKeyScanner(source).scan()
  } catch {
    // Syntax errors are reported by the caller's normal JSON parser.
    return []
  }
}

export function duplicateJsonKeyIssues(source: string): string[] {
  return duplicateJsonKeys(source).map(
    ({ path, key }) => `duplicate JSON key ${JSON.stringify(key)} at ${path}`,
  )
}
