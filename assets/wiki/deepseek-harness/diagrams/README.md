# DeepSeek Harness 辅助图

这组图服务于 [DeepSeek Harness Runtime Wiki](../../../../wiki/DSH/index.md)。正文是完整讲稿；图只展开五处不适合用连续段落表达的执行或对象关系。读者不打开图也能理解正文。

## 证据合同

- DeepSeek Harness 源码基线：`47f943859bef60e4160492346772ded9b24f765a`
- 每张图都由同目录结构化 Archify JSON 生成；HTML 是冻结交付物，不直接手改
- Archify quality profile：`showcase`
- 面向读者的标题、节点和关系使用中文；`Turn`、`SessionEvent`、`run_code`、`Activation` 等源码标识按需保留
- 每张图交付前都要通过 Archify showcase 校验，并在 light / dark、`1440x900` / `2048x1320` 下完成本地 visual-check
- visual-check 截图与回执只用于本地复核，不作为 Wiki 发布资产提交
- 自动 containment 只能证明无横纵溢出；视觉质量仍以页面 dialog 中的人工复核为准

## 当前使用的五张图

| 顺序 | 主题 | 类型 | 交互图 | Spec |
| --- | --- | --- | --- | --- |
| 01 | 一个 Session 从 Composition 到 Turn 结束 | Sequence | [HTML](13-session-composition-turn.html) | [JSON](13-session-composition-turn.sequence.json) |
| 02 | Host、Preset 与 Agent 的关系 | Architecture | [HTML](14-host-preset-agent.html) | [JSON](14-host-preset-agent.architecture.json) |
| 03 | 完整历史如何变成本轮模型输入 | Architecture | [HTML](15-history-to-model-surface.html) | [JSON](15-history-to-model-surface.architecture.json) |
| 04 | Native 与 Code 的工具调用顺序 | Architecture | [HTML](16-native-vs-code.html) | [JSON](16-native-vs-code.architecture.json) |
| 05 | 子会话与当前运行实例 | Architecture | [HTML](17-session-activation.html) | [JSON](17-session-activation.architecture.json) |

页面只创建一个无 `src` 的 iframe。读者点击某张图时才加载对应 HTML，关闭弹窗后立即卸载。
