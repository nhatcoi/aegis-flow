---
layout: home

hero:
  name: "AegisFlow"
  text: "Business Workflow & Rules Verification"
  tagline: "Kiểm chứng hình thức, SMT Solver (Z3) và Design by Contract cho ứng dụng Java & Spring Boot."
  actions:
    - theme: brand
      text: Bắt Đầu Nhanh (5 Phút)
      link: /vi/guide/getting-started
    - theme: alt
      text: Tích Hợp Spring Boot
      link: /vi/guide/spring-boot
    - theme: alt
      text: GitHub
      link: https://github.com/nhatcoi/aegis-flow

features:
  - title: Contract-Driven Design
    details: Bảo vệ toàn vẹn dữ liệu phương thức với <code>@Requires</code>, <code>@Ensures</code> và hàm <code>old(...)</code> để theo dõi biến đổi trạng thái qua thời gian.
  - title: Micro-Kernel SPI
    details: Nhân điều phối siêu nhẹ độc lập, hỗ trợ cắm-rút các engine SMT (Z3 Solver), Bounded Model Checking (BMC) và Fuzzing đa luồng.
  - title: Spring Boot 3 Native
    details: Tự động phát hiện Workflow Bean khi ứng dụng khởi động, in báo cáo Dashboard trực tiếp ra console và cung cấp REST API giám sát.
  - title: Actionable Counter-Examples
    details: Khi phát hiện vi phạm bất biến hoặc deadlock, pipeline xuất chính xác vết trạng thái (Trace) và giá trị biến vi phạm để fix bug tức thì.
---
