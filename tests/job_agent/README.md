# 求职准备模块：分类测试与学习入口

这里是原 `test_job_agent.py` 的 57 个测试，按职责拆成 7 类。
本次仅调整文件组织和假数据工具的名称，保留测试输入、检查条件和业务逻辑。
测试代码用于检查程序，不是产品实际处理简历和职位的代码。

## 分类与建议阅读顺序

| 顺序 | 文件 | 测试数 | 要理解的问题 |
| --- | --- | ---: | --- |
| 1 | [test_evidence.py](test_evidence.py) | 18 | 原文是否支持事实？工期如何分类？虚构数字如何拦截？ |
| 2 | [test_fixtures.py](test_fixtures.py) | 2 | 合成简历和招聘素材是否符合输入约束？ |
| 3 | [test_fetch_job.py](test_fetch_job.py) | 10 | 网页正文怎样读取？不安全或不可读取的响应怎样处理？ |
| 4 | [test_profile.py](test_profile.py) | 6 | 偏好和经历证据怎样校验？没有偏好时怎么办？ |
| 5 | [test_output.py](test_output.py) | 5 | 单个职位如何输出准备包、保存记录、保留人工提交边界？ |
| 6 | [test_batch.py](test_batch.py) | 11 | 多职位如何处理、去重，并在一个失败后继续？ |
| 7 | [test_ranking.py](test_ranking.py) | 5 | 排序怎样使用偏好与引用日期？未知信息如何保留？ |

[support.py](support.py) 是公共工具，不是一类业务测试：

- `fixture()`：读取相邻 `tests/fixtures/` 文件夹中的合成文字。
- `html_response()`：制造假网页响应，不发送网络请求。
- `build_test_analysis()`：制造假模型输出，不分析文字，也不调用模型。

真正的处理函数仍在 [job_agent.py](../../job_agent.py)。以后每次只读一个测试，
再对照它调用的处理函数；不需要一次理解所有文件。

## 如何运行

下面的命令都在项目根目录运行。如果尚未激活虚拟环境，使用
`.venv/bin/python` 代替 `python`。

只运行第一类：

```bash
python -m unittest -v tests.job_agent.test_evidence
```

只运行一个测试：

```bash
python -m unittest -v tests.job_agent.test_evidence.EvidenceChecks.test_unsupported_quote_cannot_confirm_eight_months
```

运行整个新文件夹（57 个测试）：

```bash
python -m unittest discover -s tests/job_agent -t . -v
```

旧入口与旧的单测试路径也继续可用：

```bash
python -m unittest -v test_job_agent.py
python -m unittest -v test_job_agent.EvidenceChecks.test_unsupported_quote_cannot_confirm_eight_months
```

根目录的 `test_job_agent.py` 只负责兼容导入与运行；请在新文件里编辑测试。
公共工具的旧名称 `make_analysis` 也保留为兼容别名，供现有其他测试使用。
默认 `unittest` 发现测试时，旧入口不会重复收集新文件夹的测试。
`python verify_week2.py` 的完整离线检查入口保持不变。

## 第一课：引用必须能在招聘原文里找到

先读 `test_evidence.py` 中的
`test_unsupported_quote_cannot_confirm_eight_months`，暂时不展开其他工期规则。

1. `build_test_analysis("8 months")` 故意制造一个声称八个月的假输出。
2. `fixture("job_term_unstated.txt")` 提供没有说明工期的合成招聘正文。
3. `check_analysis()` 检查引用是否存在于正文；不受支持的事实回到未知状态。
4. 两个现有断言检查工期值变成 `Not stated`，分类变成 `variable_or_unclear`。

这一环节检查的是“引用有没有来源”，不是“引用的意思理解得对不对”。
找到一句话，并不证明它肯定八个月、属于当前职位或仍然有效。

### 留给你的小修改

在这个测试现有断言后，自己补一个检查引用字段的断言，并填写右侧空白：

```python
self.assertEqual(a.term.source_quote, ___)
```

考虑：一个不在招聘原文中的引用，在校验之后还应该保留吗？
完成后只运行该测试，再把你填写的那一行与结果发来。
这次文件拆分没有替你添加这个断言。

## 验证边界

2026-10-07 拆分检查记录：

- 对比拆分前后的语法树：57 个测试方法的内容一致，只有假数据构造函数改名。
- 旧入口、新文件夹入口和直接运行旧文件：均通过 57 个测试。
- 新旧单测试路径：均可运行同一个测试。
- 根目录默认发现测试：收集 121 个测试，没有重复收集核心测试。
- 完整 `verify_week2.py`：121 个 Python 测试、前端语法检查和 25 个前端状态场景通过。
- 完整检查最初因环境禁止本机端口产生 20 个网页测试错误；获准临时使用回环端口后重跑通过。

这些是合成素材、模拟响应和假模型输出的离线测试，不是实际岗位验证。
它们不证明真实网页可读取、岗位仍开放、模型真实输出正确或所有语义都安全。
已发现的工期否定句误判与非数字虚构声明等问题，不会因为拆文件而消失；
本次没有修改业务校验，也没有新增这些问题的回归测试。
