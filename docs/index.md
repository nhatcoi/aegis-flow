---
layout: home

hero:
  name: "AegisFlow"
  text: "Business Workflow & Rules Verification"
  tagline: "Formal verification, SMT Solvers (Z3), and Design by Contract for Java & Spring Boot applications."
  actions:
    - theme: brand
      text: Quick Start (5 Mins)
      link: /guide/getting-started
    - theme: alt
      text: Spring Boot Integration
      link: /guide/spring-boot
    - theme: alt
      text: GitHub
      link: https://github.com/nhatcoi/aegis-flow

features:
  - title: Contract-Driven Design
    details: Enforce method preconditions and postconditions using <code>@Requires</code>, <code>@Ensures</code>, and temporal state tracking with <code>old(...)</code>.
  - title: Micro-Kernel SPI
    details: Lightweight plug-and-play architecture integrating SMT Solvers (Z3), Bounded Model Checking (BMC), and multi-threaded fuzzing.
  - title: Spring Boot 3 Native
    details: Automatically scans workflow beans upon startup, outputs verification dashboards to logs, and exposes REST endpoints.
  - title: Actionable Counter-Examples
    details: Whenever an invariant or business rule is violated, AegisFlow produces the exact state trace and variable valuations to quickly debug failures.
---
