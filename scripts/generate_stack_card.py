"""Generate assets/stack.svg: technologies detected in the code of every repo.

Reads build files (pom.xml, Gradle, package.json), Docker Compose files,
Terraform, CI definitions and deployment manifests from each repository
and matches them against the rules below. Each technology shows how many
repositories use it, so the card stays current as projects are added.

Usage: python scripts/generate_stack_card.py [--from-json FILE]
"""

import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone

from common import ACCENT, BG, FONT, TEXT, TITLE, esc, get_or_none, has_private_access, own_repos, write_asset

# (category, technology, file regex, content regex or None for "file exists").
RULES = [
    ("Backend", "Spring Boot", r"(^|/)pom\.xml$|build\.gradle", r"spring-boot"),
    ("Backend", "Spring Cloud", r"(^|/)pom\.xml$|build\.gradle", r"spring-cloud-starter"),
    ("Backend", "Spring Security", r"(^|/)pom\.xml$|build\.gradle", r"spring-boot-starter-(security|oauth2)"),
    ("Backend", "Spring Data JPA", r"(^|/)pom\.xml$|build\.gradle", r"spring-boot-starter-data-jpa"),
    ("Backend", "Spring Modulith", r"(^|/)pom\.xml$", r"spring-modulith"),
    ("Backend", "Resilience4j", r"(^|/)pom\.xml$|build\.gradle", r"resilience4j"),
    ("Backend", "gRPC", r"(^|/)pom\.xml$|package\.json$|\.proto$", r"grpc|syntax\s*="),
    ("Backend", "Node.js", r"(^|/)package\.json$", r'"(express|nodemon|@grpc/grpc-js)"'),
    ("Backend", "Flyway", r"(^|/)pom\.xml$|build\.gradle", r"flyway"),
    ("Backend", "Thymeleaf", r"(^|/)pom\.xml$", r"thymeleaf"),
    ("Backend", "JavaFX", r"(^|/)pom\.xml$", r"javafx"),
    ("Frontend", "React", r"(^|/)package\.json$", r'"react"'),
    ("Frontend", "TypeScript", r"(^|/)package\.json$", r'"typescript"'),
    ("Frontend", "Vite", r"(^|/)package\.json$", r'"vite"'),
    ("Frontend", "Tailwind CSS", r"(^|/)package\.json$", r'"tailwindcss"'),
    ("Frontend", "TanStack", r"(^|/)package\.json$", r'"@tanstack/'),
    ("Frontend", "PWA", r"(^|/)package\.json$", r'"(vite-plugin-pwa|workbox-window)"'),
    ("Mobile", "Android", r"build\.gradle(\.kts)?$", r"com\.android\.application|androidx"),
    ("Mobile", "Jetpack Compose", r"build\.gradle(\.kts)?$|libs\.versions\.toml$", r"compose"),
    ("Mobile", "Room", r"build\.gradle(\.kts)?$|libs\.versions\.toml$", r"androidx\.room|room-"),
    ("Mobile", "SQLCipher", r"build\.gradle(\.kts)?$|libs\.versions\.toml$", r"sqlcipher"),
    ("Data & Messaging", "PostgreSQL", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$|\.tf$", r"postgres"),
    ("Data & Messaging", "MySQL", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$", r"mysql"),
    ("Data & Messaging", "Redis", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$|\.tf$", r"redis|upstash"),
    ("Data & Messaging", "RabbitMQ", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$|\.tf$", r"amqp|rabbitmq|cloudamqp"),
    ("Data & Messaging", "Supabase", r"\.tf$|docker-compose.*\.ya?ml$", r"supabase"),
    ("Security", "Keycloak", r"(^|/)package\.json$|docker-compose.*\.ya?ml$|(^|/)pom\.xml$", r"keycloak"),
    ("Security", "JWT", r"(^|/)pom\.xml$|build\.gradle", r"jjwt|oauth2-resource-server"),
    ("Security", "Stripe", r"(^|/)pom\.xml$|(^|/)package\.json$", r"stripe"),
    ("Cloud & IaC", "Terraform", r"\.tf$", None),
    ("Cloud & IaC", "Azure", r"\.tf$|\.github/workflows/.*\.ya?ml$", r"azurerm|azure/login"),
    ("Cloud & IaC", "Cloudflare", r"\.tf$", r"cloudflare"),
    ("Cloud & IaC", "Netlify", r"(^|/)netlify(\.toml|/)", None),
    ("DevOps & CI/CD", "Docker", r"(^|/)Dockerfile$", None),
    ("DevOps & CI/CD", "Docker Compose", r"(^|/)docker-compose.*\.ya?ml$", None),
    ("DevOps & CI/CD", "Kubernetes", r"(^|/)(k8s|kubernetes|helm)/|(^|/)Chart\.yaml$", None),
    ("DevOps & CI/CD", "GitHub Actions", r"^\.github/workflows/.*\.ya?ml$", None),
    ("DevOps & CI/CD", "Jenkins", r"(^|/)Jenkinsfile$", None),
    ("DevOps & CI/CD", "SonarQube", r"(^|/)pom\.xml$|Jenkinsfile$|sonar-project\.properties$", r"sonar"),
    ("DevOps & CI/CD", "Trivy", r"^\.github/workflows/.*\.ya?ml$", r"trivy"),
    ("DevOps & CI/CD", "Cosign", r"^\.github/workflows/.*\.ya?ml$", r"cosign"),
    ("DevOps & CI/CD", "Maven", r"(^|/)pom\.xml$", None),
    ("DevOps & CI/CD", "Gradle", r"build\.gradle(\.kts)?$", None),
    ("Observability", "OpenTelemetry", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$", r"opentelemetry|tracing-bridge-otel"),
    ("Observability", "Prometheus", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$", r"prometheus"),
    ("Observability", "Grafana", r"docker-compose.*\.ya?ml$|\.tf$", r"grafana"),
    ("Observability", "Zipkin", r"(^|/)pom\.xml$|docker-compose.*\.ya?ml$", r"zipkin"),
    ("Testing", "JUnit 5", r"(^|/)pom\.xml$|build\.gradle", r"junit-jupiter|spring-boot-starter-test|junit5"),
    ("Testing", "Testcontainers", r"(^|/)pom\.xml$|build\.gradle", r"testcontainers"),
    ("Testing", "ArchUnit", r"(^|/)pom\.xml$", r"archunit"),
    ("Testing", "Karate", r"(^|/)pom\.xml$", r"karate"),
    ("Testing", "Cucumber", r"\.feature$", None),
    ("Testing", "Playwright", r"(^|/)package\.json$", r'"@playwright/test"'),
    ("Testing", "Vitest", r"(^|/)package\.json$", r'"vitest"'),
    ("Testing", "JaCoCo", r"(^|/)pom\.xml$", r"jacoco"),
]
CATEGORIES = list(dict.fromkeys(rule[0] for rule in RULES))
SKIP_DIRS = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.idea)/")
MAX_FILES_PER_REPO = 40


def scan_repo(repo):
    """Return the set of technologies found in one repository."""
    tree = get_or_none(f"/repos/{repo['full_name']}/git/trees/{repo['default_branch']}?recursive=1")
    if not tree:
        return set()
    paths = [t["path"] for t in tree["tree"] if t["type"] == "blob" and not SKIP_DIRS.search(t["path"])]
    found, contents = set(), {}
    wanted = [p for p in paths if any(re.search(r[2], p) and r[3] for r in RULES)]
    for path in wanted[:MAX_FILES_PER_REPO]:
        contents[path] = (get_or_none(f"/repos/{repo['full_name']}/contents/{urllib.parse.quote(path)}", raw=True) or "").lower()
    for _, tech, file_re, content_re in RULES:
        for path in paths:
            if not re.search(file_re, path):
                continue
            if content_re is None or re.search(content_re, contents.get(path, ""), re.I):
                found.add(tech)
                break
    return found


def collect():
    counts = {}
    repos = own_repos()
    for repo in repos:
        for tech in scan_repo(repo):
            counts[tech] = counts.get(tech, 0) + 1
    print(f"Scanned {len(repos)} repositories, detected {len(counts)} technologies")
    return counts, len(repos)


def render(counts, repo_count, private):
    width, pad = 830, 25
    char_w, pill_h, gap = 7.0, 22, 8
    label_w = 150
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    scope = "public &amp; private" if private else "public"

    body, y = [], 78
    for cat in CATEGORIES:
        techs = sorted(((t, counts[t]) for c, t, *_ in RULES if c == cat and t in counts),
                       key=lambda tn: (-tn[1], tn[0]))
        if not techs:
            continue
        body.append(f'<text x="{pad}" y="{y + 15}" class="c">{esc(cat)}</text>')
        x = pad + label_w
        for tech, n in techs:
            label = f"{tech}  ×{n}"
            w = len(label) * char_w + 20
            if x + w > width - pad:
                x, y = pad + label_w, y + pill_h + gap
            body.append(f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="{pill_h}" rx="11" '
                        f'fill="#1f1d31" stroke="#fe428e" stroke-opacity=".45"/>'
                        f'<text x="{x + 10:.0f}" y="{y + 15}" class="p">{esc(tech)}'
                        f'<tspan class="x">  ×{n}</tspan></text>')
            x += w + gap
        y += pill_h + gap + 6
    height = y + 12

    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Technologies detected in my code">',
        f'<style>.t{{font:600 18px {FONT};fill:{TITLE}}}.s{{font:400 12px {FONT};fill:{TEXT};opacity:.75}}'
        f'.c{{font:600 13px {FONT};fill:{ACCENT}}}.p{{font:400 12px {FONT};fill:{TEXT}}}'
        f'.x{{fill:{TITLE};font-weight:600}}</style>',
        f'<rect width="{width}" height="{height}" rx="6" fill="{BG}"/>',
        f'<text x="{pad}" y="35" class="t">Tech detected in my code</text>',
        f'<text x="{pad}" y="55" class="s">Auto-scanned build files, IaC and pipelines across '
        f'{repo_count} {scope} repositories · ×N = repositories using it · updated {updated}</text>',
    ]
    return "\n".join(head + body + ["</svg>"]) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--from-json":
        data = json.load(open(sys.argv[2]))
        counts, repo_count, private = data["counts"], data["repos"], True
    else:
        (counts, repo_count), private = collect(), has_private_access()
    if not counts:
        sys.exit("No technologies detected; leaving the existing card untouched.")
    write_asset("stack.svg", render(counts, repo_count, private))


if __name__ == "__main__":
    main()
