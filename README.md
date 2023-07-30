<p align="center">
  <img src="media/quiltix-logo-full.svg" height="170" />
</p>

----  

<div align="center">

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/PrismPipeline/QuiltiX/LICENSE)
[![Version](https://img.shields.io/github/v/release/PrismPipeline/QuiltiX/releases)](https://github.com/PrismPipeline/QuiltiX/releases/latest)
</div>

QuiltiX is a graphical node editor to edit, and author [MaterialX](https://materialx.org/) based materials of 3D assets. It includes a viewport based on [OpenUSD](https://www.openusd.org/release/index.html)'s [Hydra](https://openusd.org/release/glossary.html#hydra), which enables viewing your assets in any renderer supporting both Hydra & MaterialX.

<img align="center" padding=5 src="media/QuiltiX.png"> 

## Table of Contents  <!-- omit from toc -->

- [Requirements](#requirements)
- [Installation](#installation)
  - [From PyPi](#from-pypi)
  - [From Source](#from-source)
- [Running QuiltiX](#running-quiltix)
  - [Running QuiltiX using hython](#running-quiltix-using-hython)
- [Integrating with your environment](#integrating-with-your-environment)
  - [Adding Hydra delegates](#adding-hydra-delegates)
    - [Arnold](#arnold)
    - [Karma](#karma)
  - [Adding custom MaterialX Node definitions](#adding-custom-materialx-node-definitions)
- [Contributing](#contributing)
- [License](#license)

## Requirements
QuiltiX requires Python 3.9+ as well as compiled versions of USD and MaterialX.

## Installation
### From PyPi

```shell
pip install QuiltiX
```

If you additionally require pre-built binaries for MaterialX & USD:
```shell
pip install QuiltiX[cppdeps]
```
### From Source
1) Clone the repository

```
git clone https://github.com/PrismPipeline/QuiltiX.git
cd QuiltiX
```

2) Install the dependencies

This will install the base python dependencies, excluding any development dependencies, MaterialX & USD

```
pip install -e . 
```

<details>
  <summary>Additional install options</summary>
If you want to just install everything (Python dependencies, dev dependencies, MaterialX & USD)
```
pip install -e .[all]
```

These are the additional install options available
```
pip install -e .[usd,materialx,dev]
```
For more information see [pyproject.toml](pyproject.toml)
</details>


## Running QuiltiX

python -m QuiltiX 

### Running QuiltiX using hython

QuiltiX can be run from `hython`, which is Houdini's python executable. This way you can use Houdini's built USD and MaterialX and don't have to worry about providing your own.  
You will also be able to use Render delegates for Houdini like Karma. Read more in the [Karma](#karma) section.

<details>
  <summary>Hython instructions</summary>
You will still need some additional libraries required by QuiltiX, so it is still necessary to install the dependencies mentioned in [Installation](#installation).  
You can then execute QuiltiX while making sure that both QuiltiX and its python dependencies are in the `PYTHONPATH` environmenv variable:
```shell
cd QuiltiX_root
set PYTHONPATH=%PYTHONPATH%;./src;/path/to/python/dependencies
/path/to/hython.exe -c "from QuiltiX import quiltix;quiltix.launch()"
```

Or if you have a virtual environment
```shell
cd QuiltiX_root
/path/to/venv/Scripts/activate
set PYTHONPATH=%PYTHONPATH%;%VIRTUAL_ENV%;./src
/path/to/hython.exe -c "from QuiltiX import quiltix;quiltix.launch()"
```
> Note that currently both the Storm as well as HoudiniGL render delegates do not seem to work in QuiltiX when being launched from hython.
</details>

## Integrating with your environment
QuiltiX tries to rely as much as possible on pre-existing environment variables from MaterialX/USD to extend its systems.

Overview over the most important Environment Variables:
| Environment Variable | Purpose | Variable Type | Example |
|-|-|-|-|
| PXR_PLUGINPATH_NAME | Paths to Hydra delegate plugins | Paths | |
| PXR_MTLX_STDLIB_SEARCH_PATHS | Paths to standard MaterialX node definition locations | Paths | |
| PXR_MTLX_PLUGIN_SEARCH_PATHS | Paths to custom MaterialX node definition locations | Paths | |
| HD_DEFAULT_RENDERER | Name of the default Hydra delegate for the viewport | String | GL |

### Adding [Hydra delegates](https://openusd.org/release/glossary.html#hydra)
> **_NOTE_**  
> The Hydra renderer needs to support MaterialX for it to work in QuiltiX.  


**_What is a Hdyra Delegate?_**  
"Hydra Render Delegates are bridges between the Hydra viewport and a renderer. They were created by Pixar as part of the Hydra renderer used in usdview. The Hydra Render Delegate system allows the ability to switch out the backend renderer for the viewport data in Hydra. [...]"<sup>[[src]](https://learn.foundry.com/katana/dev-guide/Plugins/HydraRenderDelegates/Introduction.html#what-is-a-hydra-render-delegate)</sup>

The [Storm Hydra Delegate](https://openusd.org/dev/api/hd_storm_page_front.html) by Pixar is both shipped with USD and enabled per default in QuiltiX. 

> ❗Adding additional Hydra delegates can, depending on the renderer, be a non-trivial task due to the need of matching USD (and potentially MaterialX) versions for the compiled binaries. Some renderers also need additional configuration for additional features like renderer specific procedurals or shaders.

To register a Hydra renderer plugin the Hydra plugin directory of the renderer needs to be added to the `PXR_PLUGINPATH_NAME` environment variable. Generally renderers also need their binaries added to the `PATH` enviornment variable, but there might be additional variables for licensing or additional features.  

Below is a non-exhaustive list of install instructions for Hydra renderers.

#### Arnold

To use Arnold in QuiltiX we require 
* [Arnold SDK](https://arnoldrenderer.com/download/#arnold-sdk)
* A compiled version of [arnold-usd](https://github.com/Autodesk/arnold-usd)


<details>
  <summary>Full Arnold install instructions</summary>

The SDK (v7.2.1.0) can be downloaded from [here](https://arnoldrenderer.com/download/product-download/?id=5408). Extract it to a favoured directory.  
To install a compiled version of arnold-usd one can download it from [here](#TODO)(v7.2.1.0) or install from [source](https://github.com/Autodesk/arnold-usd)

Afterward couple of enviornment variables need to be set
```shell
set PATH=%PATH%;SDK_EXTRACT_DIR/bin
set PXR_PLUGINPATH_NAME=%PXR_PLUGINPATH_NAME%;ARNOLD_USD_DIR/plugin
``` 

</details>

#### Karma
To run Karma you need to execute QuiltiX from [hython](#running-quiltix-using-hython).

It is possible to use additional Hydra delegates, which are available in the Houdini environment.

#### Changing the active Hydra delegate <!-- omit from toc -->
The default Hydra delegate can be changed by setting the `HD_DEFAULT_RENDERER` environment variable to the preferred renderer.

```shell
set HD_DEFAULT_RENDERER="GL"
```

After opening QuiltiX the active Hydra delegate can be changed in the "View" -> "Set Renderer" menu.



### Adding custom MaterialX Node definitions

To add custom MaterialX node defintions they can be added by adding the location of the node definition files to the `PXR_MTLX_PLUGIN_SEARCH_PATHS` environment variable.


## Contributing

We welcome contributions to the QuiltiX! If you'd like to contribute, please follow these steps:

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Submit a pull request.

## License

QuiltiX is licensed under the Apache License. See [LICENSE](LICENSE) for more information.
