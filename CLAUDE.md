# Local working folder is '/workspace'
- Never out of this path!!!

# Active 'finmind'  of Python Virtual Env
- path: '/workspace/finmind'
- Active 'finmind' venv first before launch a linux command.
- All python packages were installed in 'finmind' venv.
- Each python is redirect to the one of 'fimmind' env.
- Example to active 'finmind' venv  command
```shell
~/.local/bin/uv run --python finmind python -c "import pandas"  
```

# File tree
/workspacetree
    ├── finmind (python virtual env)
    ├── logs (all markdown files of discussion of Cloude Code)
    └── playground (workspace for jupyter notebook)