# E2E Bug Report — Template
**Test Run**: `{{TEST_NAME}}`
**Discovered**: {{DATE}}
**Severity**: {{CRITICAL|HIGH|MEDIUM|LOW}}
**Git SHAs**: OPP `{{OPP_SHA}}` / OL `{{OL_SHA}}` / ORF `{{ORF_SHA}}`

---

## 1. Bug ID & Title

**E2E-{{ID}}**: {{SHORT_DESCRIPTION}}

---

## 2. 问题现象

{{DETAILED_DESCRIPTION}}

---

## 3. 根因分析

**工具**: {{OPP|OL|ORF}} {{CLI|MCP}}
**涉及文件**:
```
{{FILE_PATHS}}
```

**根因**:

{{ROOT_CAUSE_EXPLANATION}}

---

## 4. 可复现

| 条件 | 值 |
|------|-----|
| 触发方式 | `{{REPRO_CMD}}` |
| 预期行为 | {{EXPECTED}} |
| 实际行为 | {{ACTUAL}} |
| 复现率 | 100% / 间歇 / 首次 |

---

## 5. 影响范围

{{AFFECTED_PATHS}}

---

## 6. 修复状态

- [ ] 已确认根因
- [ ] 已创建回归测试
- [ ] 已修复
- [ ] 已验证

**修复 commit**: `{{FIX_COMMIT}}`
**修复时间**: {{DATE}}

---

## 7. 修复验证

```bash
{{VERIFICATION_CMD}}
```
预期: {{VERIFICATION_EXPECT}}

---

## 8. 附录：相关日志

```
{{LOG_EXCERPT}}
```
