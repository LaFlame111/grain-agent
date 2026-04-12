# GitCode 配置指南

本指南将帮助您在IDE中配置GitCode代码托管服务。

## 前置准备

### 1. 注册GitCode账户
- 访问 https://gitcode.net
- 注册并登录您的账户

### 2. 创建仓库
- 登录后，点击右上角的 "+" 或 "新建仓库"
- 填写仓库名称（例如：grain_agent）
- 选择仓库可见性（公开/私有）
- 点击"创建仓库"

## 配置步骤

### 方法一：使用HTTPS（推荐新手）

#### 1. 配置Git用户信息（如果还没配置）
```bash
git config --global user.name "您的用户名"
git config --global user.email "您的邮箱"
```

#### 2. 添加GitCode远程仓库
```bash
git remote add origin https://gitcode.net/您的用户名/仓库名.git
```

例如（使用您的账户 lorexiao）：
```bash
git remote add origin https://gitcode.net/lorexiao/grain_agent.git
```

#### 3. 验证远程仓库配置
```bash
git remote -v
```

应该看到：
```
origin  https://gitcode.net/您的用户名/仓库名.git (fetch)
origin  https://gitcode.net/您的用户名/仓库名.git (push)
```

#### 4. 首次推送代码
```bash
# 添加所有文件
git add .

# 提交代码
git commit -m "Initial commit"

# 推送到GitCode
git push -u origin main
# 或者如果您的默认分支是master，使用：
# git push -u origin master
```

**注意**：首次推送时，GitCode会要求您输入用户名和密码（或访问令牌）。

### 方法二：使用SSH（推荐，更安全）

#### 1. 生成SSH密钥（如果还没有）
```bash
ssh-keygen -t ed25519 -C "lorexiao@163.com"
```

按提示操作：
- 按Enter使用默认文件位置
- 可以设置密码短语（可选，但推荐）

#### 2. 查看公钥内容
```bash
cat ~/.ssh/id_ed25519.pub
# Windows PowerShell:
cat $env:USERPROFILE\.ssh\id_ed25519.pub
```

复制输出的公钥内容。

#### 3. 在GitCode中添加SSH密钥
- 登录GitCode
- 点击右上角头像 → "设置" → "SSH密钥"
- 点击"添加密钥"
- 粘贴您的公钥
- 填写标题（例如：我的电脑）
- 点击"添加密钥"

#### 4. 测试SSH连接
```bash
ssh -T git@gitcode.net
```

如果看到类似 "Hi username! You've successfully authenticated..." 的提示，说明配置成功。

#### 5. 添加GitCode远程仓库（使用SSH）
```bash
git remote add origin git@gitcode.net:您的用户名/仓库名.git
```

例如（使用您的账户 lorexiao）：
```bash
git remote add origin git@gitcode.net:lorexiao/grain_agent.git
```

#### 6. 首次推送代码
```bash
git add .
git commit -m "Initial commit"
git push -u origin main
```

## 常用Git命令

### 查看状态
```bash
git status
```

### 查看远程仓库
```bash
git remote -v
```

### 修改远程仓库地址
```bash
# 删除现有远程仓库
git remote remove origin

# 添加新的远程仓库
git remote add origin <新的仓库地址>
```

### 拉取最新代码
```bash
git pull origin main
```

### 推送代码
```bash
git push origin main
```

### 查看提交历史
```bash
git log
```

## 在IDE中配置（Cursor/VSCode）

### 1. 使用内置Git功能
- 打开源代码管理面板（Ctrl+Shift+G）
- 可以看到所有更改的文件
- 点击"+"暂存文件
- 输入提交信息
- 点击"✓"提交
- 点击"..." → "推送"推送到GitCode

### 2. 使用终端
- 打开集成终端（Ctrl+`）
- 使用上述Git命令进行操作

## 常见问题

### Q: 推送时提示认证失败？
A: 
- HTTPS方式：检查用户名和密码（或访问令牌）是否正确
- SSH方式：确认SSH密钥已正确添加到GitCode

### Q: 如何创建访问令牌（Token）？
A:
- 登录GitCode → 设置 → 访问令牌
- 创建新令牌，选择权限（至少需要repo权限）
- 复制令牌，推送时密码处输入令牌

### Q: 如何切换远程仓库？
A:
```bash
git remote set-url origin <新的仓库地址>
```

### Q: 如何查看当前分支？
A:
```bash
git branch
```

### Q: 如何创建新分支？
A:
```bash
git checkout -b 新分支名
```

## 下一步

配置完成后，您可以：
1. 在GitCode网页上查看您的代码
2. 使用GitCode的Issue功能跟踪问题
3. 使用Pull Request功能进行代码审查
4. 邀请团队成员协作

## 参考资源

- GitCode官方文档：https://gitcode.net/help
- Git官方文档：https://git-scm.com/doc
- Git教程：https://git-scm.com/book/zh/v2
