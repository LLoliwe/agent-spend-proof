# Agent instructions

Before proposing any paid GPU resources, read [docs/GPU_COST_GATE.md](docs/GPU_COST_GATE.md). This is a read-only comparison policy, not approval to rent GPUs, self-host tools, connect billing or spend. Record supplier-direct evidence and project approval in PRY-223. No GPU requirement means no procurement.

## Optional Pryntor Anatomy visualization capability (PRY-225)

Anatomy is an opt-in, MIT-licensed agent skill for interactive isometric SVG/WebGL and experimental 3D technical explainers. It is **not** a mandatory production/runtime dependency.

- Canonical skill/installer: https://github.com/LLoliwe/Anthropic-skills/tree/main/skills/pryntor-anatomy
- Pinned official source: `wheresryan22/anatomy@e9488296a44211c42701ff71705b7901470ec78f`
- Only for an actual visual explainer task, in an appropriate checkout: `bash /path/to/Anthropic-skills/skills/pryntor-anatomy/install.sh .`
- Never silently install at startup, overwrite existing agent skills, buy cloud/GPU compute, upload private inputs or publish to a public community gallery.
- Technical diagrams need mathematically correct models, browser and screenshot QA, keyboard/reduced-motion/accessibility review. They are not engineering certification or safety evidence.
- Record actual per-project installation and checks before claiming deployment. Source and remaining gates: https://linear.app/pryntor/issue/PRY-225.
