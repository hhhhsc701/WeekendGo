## ADDED Requirements

### Requirement: 保存行程到数据库

系统 SHALL 将生成的行程数据保存到 SQLite 数据库。

#### Scenario: 行程保存成功

- **WHEN** 行程生成完成
- **THEN** 系统将行程写入数据库并返回行程 ID

#### Scenario: 数据库写入失败

- **WHEN** 数据库不可用或写入失败
- **THEN** 系统返回 500 错误并记录日志

### Requirement: 查询行程详情

系统 SHALL 根据行程 ID 查询并返回完整行程数据。

#### Scenario: 行程存在

- **WHEN** 请求有效的行程 ID
- **THEN** 返回完整的 TripOutput 数据

#### Scenario: 行程不存在

- **WHEN** 请求不存在的行程 ID
- **THEN** 返回 404 错误

### Requirement: 查询行程列表

系统 SHALL 返回用户保存的所有行程列表。

#### Scenario: 存在多条行程

- **WHEN** 数据库有多条行程记录
- **THEN** 返回行程列表，包含 ID、城市、日期、创建时间摘要

#### Scenario: 无行程记录

- **WHEN** 数据库无行程记录
- **THEN** 返回空列表

### Requirement: 更新行程数据

系统 SHALL 支持更新已保存的行程（如调整后重新保存）。

#### Scenario: 行程更新成功

- **WHEN** 用户调整行程后请求保存
- **THEN** 更新数据库中的行程数据并更新时间戳

### Requirement: 删除行程

系统 SHALL 支持删除已保存的行程。

#### Scenario: 行程删除成功

- **WHEN** 用户请求删除行程
- **THEN** 从数据库移除行程记录并返回成功