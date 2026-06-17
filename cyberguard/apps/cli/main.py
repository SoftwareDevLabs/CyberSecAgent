from __future__ import annotations

try:
    import typer
except ImportError:  # pragma: no cover
    typer = None


if typer:
    app = typer.Typer(name="cyberguard")

    sbom_app = typer.Typer()
    vuln_app = typer.Typer()
    risk_app = typer.Typer()
    compliance_app = typer.Typer()
    incident_app = typer.Typer()
    pentest_app = typer.Typer()
    fuzz_app = typer.Typer()
    agent_app = typer.Typer()

    @sbom_app.command("generate")
    def sbom_generate(source: str = ".", output: str = "sbom.cdx.json", format: str = "cyclonedx") -> None:
        typer.echo(f"generate {format} from {source} -> {output}")

    @sbom_app.command("submit")
    def sbom_submit(file: str, product: str, version: str, domain: str) -> None:
        typer.echo(f"submit {file} for {product}@{version} ({domain})")

    @sbom_app.command("scan")
    def sbom_scan(sbom_id: str, threshold: str = "HIGH", fail_on_critical: bool = False) -> None:
        typer.echo(f"scan {sbom_id} threshold={threshold} fail_on_critical={fail_on_critical}")

    @sbom_app.command("diff")
    def sbom_diff(from_id: str = typer.Option(..., "--from"), to: str = typer.Option(..., "--to")) -> None:
        typer.echo(f"diff {from_id} -> {to}")

    @vuln_app.command("search")
    def vuln_search(cve: str) -> None:
        typer.echo(f"search {cve}")

    @vuln_app.command("report")
    def vuln_report(sbom_id: str, output: str, format: str = "pdf") -> None:
        typer.echo(f"report for {sbom_id} -> {output} ({format})")

    @risk_app.command("score")
    def risk_score(sbom_id: str, domain: str, asil: str | None = None) -> None:
        typer.echo(f"risk score {sbom_id} domain={domain} asil={asil}")

    @compliance_app.command("check")
    def compliance_check(standard: str, product: str) -> None:
        typer.echo(f"check {standard} for {product}")

    @compliance_app.command("report")
    def compliance_report(standard: str, output: str) -> None:
        typer.echo(f"report {standard} -> {output}")

    @incident_app.command("create")
    def incident_create(severity: str, description: str, sbom_id: str) -> None:
        typer.echo(f"incident severity={severity} sbom={sbom_id}: {description}")

    @pentest_app.command("run")
    def pentest_run(target: str, type: str = "api-scan") -> None:
        typer.echo(f"pentest {type} on {target}")

    @fuzz_app.command("run")
    def fuzz_run(target: str, protocol: str, duration: int = 3600) -> None:
        typer.echo(f"fuzz {protocol} on {target} for {duration}s")

    @agent_app.command("chat")
    def agent_chat() -> None:
        typer.echo("Starting interactive agent chat...")

    @agent_app.command("ask")
    def agent_ask(question: str) -> None:
        typer.echo(question)

    app.add_typer(sbom_app, name="sbom")
    app.add_typer(vuln_app, name="vuln")
    app.add_typer(risk_app, name="risk")
    app.add_typer(compliance_app, name="compliance")
    app.add_typer(incident_app, name="incident")
    app.add_typer(pentest_app, name="pentest")
    app.add_typer(fuzz_app, name="fuzz")
    app.add_typer(agent_app, name="agent")
else:
    app = None


if __name__ == "__main__" and typer:
    app()
