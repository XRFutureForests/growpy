# GrowPy Config Templates (packaged defaults)

This directory ships **default TOMLs and the species lookup CSV** inside the
installed growpy package. They are resolved as fallbacks when a user has not
overridden them in the repository-root `config/` directory.

**Do not edit these files in your local install.** To customize configuration,
edit the copies in the project-root [`config/`](../../../../config/)
directory, which take precedence over these packaged defaults.

See [`config/README.md`](../../../../config/README.md) for the full
configuration model and resolution order.
