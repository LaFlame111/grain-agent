# Marp 使用说明文档

## 📋 什么是 Marp？

**Marp** (Markdown Presentation Ecosystem) 是一个将 Markdown 文件转换为演示文稿的工具。

**特点：**
- ✅ 使用 Markdown 语法编写演示文稿
- ✅ 支持转换为 PPTX、PDF、HTML 等多种格式
- ✅ 支持主题自定义
- ✅ 支持图片、代码块、表格等丰富内容
- ✅ 命令行工具，易于集成到工作流

**适用场景：**
- 技术分享演示文稿
- 项目汇报文档
- 培训材料制作
- 快速生成演示文稿

---

## 🚀 安装 Marp

### 前置要求

**需要安装 Node.js 和 npm**
- Node.js 版本：建议 v14.0.0 或更高版本
- npm 版本：建议 v6.0.0 或更高版本

**检查是否已安装：**
```bash
node --version
npm --version
```

**如果未安装：**
- 访问 [Node.js 官网](https://nodejs.org/) 下载安装
- 安装 Node.js 时会自动安装 npm

---

### 安装 Marp CLI

**全局安装（推荐）：**
```bash
npm install -g @marp-team/marp-cli
```

**验证安装：**
```bash
marp --version
```

**预期输出：**
```
@marp-team/marp-cli v4.2.3 (w/ @marp-team/marp-core v4.2.0)
```

---

## 📝 Markdown 文件格式要求

### 基本格式

**1. 文件开头添加 Marp 配置（必需）**

```markdown
---
marp: true
theme: default
paginate: true
header: '文档标题'
footer: '页脚信息'
size: 16:9
---
```

**配置说明：**
- `marp: true`: 启用 Marp 模式
- `theme`: 主题（default, gaia, uncover 等）
- `paginate`: 是否显示页码
- `header`: 页眉内容
- `footer`: 页脚内容
- `size`: 幻灯片尺寸（16:9, 4:3, A4 等）

**2. 使用 `---` 分隔幻灯片**

```markdown
---
marp: true
---

# 第1页：标题

这是第一页的内容

---

# 第2页：标题

这是第二页的内容

---
```

**重要：** `---` 必须单独成行，前后有空行

---

### 支持的 Markdown 语法

**标题：**
```markdown
# 一级标题
## 二级标题
### 三级标题
```

**列表：**
```markdown
- 无序列表项1
- 无序列表项2

1. 有序列表项1
2. 有序列表项2
```

**代码块：**
````markdown
```python
def hello():
    print("Hello, World!")
```
````

**表格：**
```markdown
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据1 | 数据2 | 数据3 |
```

**图片：**
```markdown
![图片描述](图片路径.png)
```

**链接：**
```markdown
[链接文本](https://example.com)
```

**粗体和斜体：**
```markdown
**粗体文本**
*斜体文本*
```

---

## 🎯 使用方法

### 基本转换命令

**转换为 PPTX（默认模式，内容为图片）：**
```bash
marp input.md --pptx --output output.pptx
```

**转换为可编辑 PPTX（实验性，需要 LibreOffice）：**
```bash
marp input.md --pptx --pptx-editable --output output.pptx
```

**注意：** 默认模式下，Marp 会将幻灯片渲染为图片插入 PPTX，这是为了确保格式一致性。如果需要可编辑文本，需要使用 `--pptx-editable` 选项（需要安装 LibreOffice）。

**转换为 PDF：**
```bash
marp input.md --pdf --output output.pdf
```

**转换为 HTML：**
```bash
marp input.md --html --output output.html
```

---

### 常用选项

**允许访问本地文件（包含图片）：**
```bash
marp input.md --pptx --allow-local-files --output output.pptx
```

**指定主题：**
```bash
marp input.md --pptx --theme gaia --output output.pptx
```

**指定幻灯片尺寸：**
```bash
marp input.md --pptx --size 16:9 --output output.pptx
```

**启用分页：**
```bash
marp input.md --pptx --paginate --output output.pptx
```

**组合使用：**
```bash
marp input.md --pptx --allow-local-files --theme default --size 16:9 --paginate --output output.pptx
```

---

## 📊 实际案例：V006 项目 PPT 转换

### 转换步骤

**1. 准备 Markdown 文件**
- 文件：`V006项目技术分享PPT.md`
- 位置：`V006/` 目录

**2. 添加 Marp 配置**
在文件开头添加：
```markdown
---
marp: true
theme: default
paginate: true
header: 'V006 粮情分析智能体项目'
footer: '技术团队 | 2025-12-19'
size: 16:9
---
```

**3. 执行转换命令**
```bash
cd V006
marp "V006项目技术分享PPT.md" --pptx --allow-local-files --output "V006项目技术分享PPT.pptx"
```

**4. 验证输出**
```bash
# 检查文件是否存在
Test-Path "V006项目技术分享PPT.pptx"
```

---

### 转换结果

**成功输出：**
```
[  INFO ] Converting 1 markdown...
[  WARN ] Insecure local file accessing is enabled for conversion from
          V006项目技术分享PPT.md.
[  INFO ] V006项目技术分享PPT.md => V006项目技术分享PPT.pptx
```

**生成文件：**
- `V006项目技术分享PPT.pptx` (PPTX 格式)

---

## ⚠️ 常见问题与解决方案

### 问题1：图片无法显示

**错误信息：**
```
[  WARN ] Marp CLI has detected accessing to local file. That is blocked by
          security reason.
```

**解决方案：**
使用 `--allow-local-files` 选项：
```bash
marp input.md --pptx --allow-local-files --output output.pptx
```

---

### 问题2：PDF 链接无法点击

**问题描述：**
Markdown 中的 PDF 链接在 PPTX 中显示为文本，无法点击。

**解决方案：**
1. **方案1：截图插入**
   - 打开 PDF 文件
   - 截图需要的页面
   - 在 Markdown 中使用图片引用

2. **方案2：保留为文本链接**
   - PPTX 中会显示为文本
   - 可以手动添加超链接

3. **方案3：转换为 HTML 后插入**
   - 先转换为 HTML
   - 在 HTML 中处理 PDF 链接
   - 再转换为 PPTX

---

### 问题3：中文文件名乱码

**问题描述：**
Windows 系统下中文文件名可能显示为乱码。

**解决方案：**
1. **使用引号包裹文件名：**
   ```bash
   marp "V006项目技术分享PPT.md" --pptx --output "V006项目技术分享PPT.pptx"
   ```

2. **使用英文文件名：**
   ```bash
   marp "presentation.md" --pptx --output "presentation.pptx"
   ```

---

### 问题4：转换后的 PPTX 全是图片，无法编辑文本

**问题描述：**
生成的 PPTX 文件中，所有内容都是图片格式，无法直接编辑文本。

**原因说明：**
这是 Marp 的**默认行为**。Marp 会将每张幻灯片渲染为图片后插入 PPTX，以确保：
- ✅ 格式一致性：在不同平台和软件中显示效果一致
- ✅ 样式保持：CSS 样式和布局完全保留
- ✅ 兼容性好：避免字体、布局等问题

**解决方案：**

**方案1：使用可编辑模式（实验性功能）**
```bash
marp input.md --pptx --pptx-editable --output output.pptx
```

**前置要求：**
- 需要安装 LibreOffice
- 这是实验性功能，可能不稳定

**安装 LibreOffice（可选）：**
- Windows: 下载安装包 https://www.libreoffice.org/download/
- 安装后确保 `soffice` 命令可用

**方案2：在 PowerPoint 中手动编辑**
- 虽然内容是图片，但可以在 PowerPoint 中：
  - 添加文本框覆盖需要修改的内容
  - 使用 PowerPoint 的"选择窗格"管理图层
  - 调整图片大小和位置

**方案3：修改源 Markdown 文件**
- 直接修改 Markdown 源文件
- 重新运行转换命令
- 这是最推荐的方式（版本控制友好）

**方案4：使用其他工具**
- 考虑使用 `pandoc` 等其他工具
- 或直接在 PowerPoint 中手动创建

**推荐做法：**
- ✅ 保持 Markdown 源文件作为"单一数据源"
- ✅ 需要修改时，修改 Markdown 文件后重新转换
- ✅ 将 Markdown 文件纳入版本控制

---

### 问题5：幻灯片格式不符合预期

**问题描述：**
生成的 PPTX 格式、布局不符合预期。

**解决方案：**
1. **调整 Marp 配置：**
   ```markdown
   ---
   marp: true
   theme: gaia          # 尝试不同主题
   size: 16:9          # 调整尺寸
   paginate: true      # 启用/禁用页码
   ---
   ```

2. **使用自定义 CSS：**
   ```markdown
   ---
   marp: true
   style: |
     section {
       font-size: 24px;
     }
   ---
   ```

3. **在 PowerPoint 中手动调整：**
   - 打开生成的 PPTX
   - 使用 PowerPoint 的格式工具调整

---

### 问题6：代码块格式不正确

**问题描述：**
代码块在 PPTX 中显示格式混乱。

**解决方案：**
1. **指定代码语言：**
   ````markdown
   ```python
   # 代码内容
   ```
   ````

2. **使用代码高亮主题：**
   ```markdown
   ---
   marp: true
   style: |
     code {
       background-color: #f5f5f5;
       padding: 2px 4px;
     }
   ---
   ```

---

## 🎨 主题选择

### 内置主题

**default（默认主题）：**
- 简洁的白色背景
- 适合正式场合

**gaia（盖亚主题）：**
- 深色背景
- 适合技术分享

**uncover（揭示主题）：**
- 现代设计风格
- 适合创意展示

**使用主题：**
```bash
marp input.md --pptx --theme gaia --output output.pptx
```

---

## 📚 高级功能

### 1. 自定义 CSS 样式

```markdown
---
marp: true
style: |
  section {
    background-color: #f0f0f0;
    font-family: 'Microsoft YaHei', sans-serif;
  }
  h1 {
    color: #0066cc;
  }
---
```

### 2. 背景图片

```markdown
---
marp: true
style: |
  section {
    background-image: url('background.jpg');
  }
---
```

### 3. 分栏布局

```markdown
---
marp: true
---

## 两栏布局

<div style="display: flex;">

<div style="flex: 1;">

**左栏内容**
- 项目1
- 项目2

</div>

<div style="flex: 1;">

**右栏内容**
- 项目3
- 项目4

</div>

</div>
```

---

## 🔧 命令行选项参考

### 常用选项

| 选项 | 说明 | 示例 |
|------|------|------|
| `--pptx` | 转换为 PPTX 格式（默认图片模式） | `--pptx` |
| `--pptx-editable` | 转换为可编辑 PPTX（实验性，需要 LibreOffice） | `--pptx-editable` |
| `--pdf` | 转换为 PDF 格式 | `--pdf` |
| `--html` | 转换为 HTML 格式 | `--html` |
| `--output` | 指定输出文件 | `--output file.pptx` |
| `--allow-local-files` | 允许访问本地文件 | `--allow-local-files` |
| `--theme` | 指定主题 | `--theme gaia` |
| `--size` | 指定尺寸 | `--size 16:9` |
| `--paginate` | 显示页码 | `--paginate` |
| `--html-as-image` | HTML 转图片 | `--html-as-image` |

### 完整命令示例

```bash
marp input.md \
  --pptx \
  --allow-local-files \
  --theme default \
  --size 16:9 \
  --paginate \
  --output output.pptx
```

---

## 📖 参考资源

### 官方文档
- **Marp 官网**: https://marp.app/
- **Marp CLI 文档**: https://github.com/marp-team/marp-cli
- **Marp 主题**: https://github.com/marp-team/marp-themes

### 相关工具
- **Marp for VS Code**: VS Code 扩展，支持实时预览
- **Marp Web**: 在线编辑器，无需安装

---

## ✅ 快速开始检查清单

**安装步骤：**
- [ ] 检查 Node.js 和 npm 是否已安装
- [ ] 运行 `npm install -g @marp-team/marp-cli`
- [ ] 验证安装：`marp --version`

**使用步骤：**
- [ ] 准备 Markdown 文件
- [ ] 在文件开头添加 Marp 配置
- [ ] 使用 `---` 分隔幻灯片
- [ ] 运行转换命令
- [ ] 检查生成的 PPTX 文件

**常见问题：**
- [ ] 图片无法显示 → 使用 `--allow-local-files`
- [ ] 中文文件名乱码 → 使用引号包裹文件名
- [ ] 格式不符合预期 → 调整主题或使用自定义 CSS

---

## 🎯 总结

Marp 是一个强大的 Markdown 转演示文稿工具，特别适合：

- ✅ **技术团队**：快速生成技术分享 PPT
- ✅ **项目汇报**：使用 Markdown 编写，自动转换为 PPT
- ✅ **文档驱动**：代码和文档统一管理

**优势：**
- 使用 Markdown 语法，简单易学
- 版本控制友好（Markdown 是文本格式）
- 支持多种输出格式
- 命令行工具，易于自动化
- 格式一致性好（渲染为图片）

**注意事项：**
- ⚠️ **默认模式下 PPTX 内容是图片**：这是 Marp 的默认行为，确保格式一致性
- ⚠️ **需要编辑时修改源文件**：推荐修改 Markdown 源文件后重新转换
- ⚠️ **可编辑模式需要 LibreOffice**：`--pptx-editable` 是实验性功能

**建议：**
- 将 Markdown 文件纳入版本控制
- 使用主题保持一致性
- 图片使用相对路径，便于管理
- 需要修改时，修改 Markdown 文件后重新转换（而不是直接编辑 PPTX）
- 定期检查生成的 PPTX 格式

---

**文档版本**: 1.0  
**最后更新**: 2025-12-19  
**适用版本**: Marp CLI v4.2.3

