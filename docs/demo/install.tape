# install.tape: install the crystal loop into a brand new project.
# Record with docs/demo/record.sh (it checks the output for private data). Never run bare.
Output "docs/demo/install.gif"
Output "docs/demo/out/install.txt"
Source "docs/demo/common.tape"
Set FontSize 14
Set Height 1080

Hide
Type "exec sh docs/demo/fixture.sh install" Enter
Sleep 4s
Show

Type "# 1. a brand new project" Enter
Sleep 400ms
Type "mkdir my-project && cd my-project && git init -q" Enter
Sleep 800ms
Type "# 2. run the installer from a copy of crystal-memory" Enter
Sleep 400ms
Type "sh ~/crystal-memory/install.sh" Enter
Sleep 7s
Type "clear" Enter
Sleep 300ms
Type "# 3. what it added: the loop, and three starter crystals" Enter
Sleep 400ms
Type "ls scripts memory/crystals" Enter
Sleep 5s
