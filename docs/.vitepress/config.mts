import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "AegisFlow",
  description: "Business Workflow & Domain Rules Verification Framework for Java & Spring Boot",

  locales: {
    root: {
      label: 'English',
      lang: 'en',
      themeConfig: {
        siteTitle: 'AegisFlow',

        nav: [
          { text: 'Guide', link: '/guide/getting-started' },
          { text: 'Spring Boot', link: '/guide/spring-boot' },
          { text: 'DSL Spec', link: '/reference/dsl-spec' },
          { text: 'Architecture', link: '/reference/architecture' },
          { text: 'FAQ', link: '/reference/faq' },
          { text: 'Changelog', link: '/guide/changelog' }
        ],

        sidebar: [
          {
            text: 'Getting Started',
            items: [
              { text: 'Overview & Problem', link: '/guide/overview' },
              { text: 'Quick Start (5 Mins)', link: '/guide/getting-started' },
              { text: 'Your First Workflow', link: '/guide/first-workflow' },
              { text: 'Changelog & Releases', link: '/guide/changelog' }
            ]
          },
          {
            text: 'User Guide',
            items: [
              { text: 'Annotations DSL', link: '/guide/annotations' },
              { text: 'Design by Contract', link: '/guide/design-by-contract' },
              { text: 'Invariants & Business Rules', link: '/guide/invariants-rules' }
            ]
          },
          {
            text: 'Spring Boot Integration',
            items: [
              { text: 'AutoConfiguration Starter', link: '/guide/spring-boot' },
              { text: 'Configuration & REST API', link: '/guide/spring-boot-api' }
            ]
          },
          {
            text: 'Technical & Specifications',
            items: [
              { text: 'Mini DSL Grammar', link: '/reference/dsl-spec' },
              { text: 'Micro-Kernel Architecture & SPI', link: '/reference/architecture' },
              { text: 'Formal Verification Foundations', link: '/reference/topics-analysis' }
            ]
          },
          {
            text: 'Reference',
            items: [
              { text: 'FAQ & Library Comparison', link: '/reference/faq' }
            ]
          }
        ],

        docFooter: {
          prev: 'Previous page',
          next: 'Next page'
        },

        footer: {
          message: 'Designed with a Software Engineering mindset.',
          copyright: 'Copyright © 2026 AegisFlow Contributors. Released under MIT License.'
        }
      }
    },
    vi: {
      label: 'Tiếng Việt',
      lang: 'vi',
      link: '/vi/',
      themeConfig: {
        siteTitle: 'AegisFlow',

        nav: [
          { text: 'Hướng Dẫn', link: '/vi/guide/getting-started' },
          { text: 'Spring Boot', link: '/vi/guide/spring-boot' },
          { text: 'Đặc Tả DSL', link: '/vi/reference/dsl-spec' },
          { text: 'Kiến Trúc', link: '/vi/reference/architecture' },
          { text: 'FAQ', link: '/vi/reference/faq' },
          { text: 'Changelog', link: '/vi/guide/changelog' }
        ],

        sidebar: [
          {
            text: 'Bắt Đầu',
            items: [
              { text: 'Tổng Quan & Bài Toán', link: '/vi/guide/overview' },
              { text: 'Cài Đặt (5 Phút)', link: '/vi/guide/getting-started' },
              { text: 'Workflow Đầu Tiên', link: '/vi/guide/first-workflow' },
              { text: 'Lịch Sử Thay Đổi (Changelog)', link: '/vi/guide/changelog' }
            ]
          },
          {
            text: 'Cẩm Nang Sử Dụng',
            items: [
              { text: 'Hệ Thống Annotations', link: '/vi/guide/annotations' },
              { text: 'Design by Contract', link: '/vi/guide/design-by-contract' },
              { text: 'Bất Biến & Luật Nghiệp Vụ', link: '/vi/guide/invariants-rules' }
            ]
          },
          {
            text: 'Tích Hợp Spring Boot',
            items: [
              { text: 'AutoConfiguration Starter', link: '/vi/guide/spring-boot' },
              { text: 'Cấu Hình & REST API', link: '/vi/guide/spring-boot-api' }
            ]
          },
          {
            text: 'Kỹ Thuật & Đặc Tả',
            items: [
              { text: 'Ngữ Pháp Biểu Thức Mini DSL', link: '/vi/reference/dsl-spec' },
              { text: 'Kiến Trúc Micro-Kernel & SPI', link: '/vi/reference/architecture' },
              { text: 'Phân Tích Đề Tài Kiểm Chứng', link: '/vi/reference/topics-analysis' }
            ]
          },
          {
            text: 'Tham Khảo',
            items: [
              { text: 'FAQ & So Sánh Thư Viện', link: '/vi/reference/faq' }
            ]
          }
        ],

        docFooter: {
          prev: 'Trang trước',
          next: 'Trang tiếp theo'
        },

        footer: {
          message: 'Phát triển theo định hướng Kỹ nghệ Phần mềm (Software Engineering).',
          copyright: 'Copyright © 2026 AegisFlow Contributors. Phát hành theo giấy phép MIT License.'
        }
      }
    }
  },

  themeConfig: {
    search: {
      provider: 'local'
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/nhatcoi/atpm-fw' }
    ]
  }
})
