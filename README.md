# STAMapper

## Overview
STAMapper is a method that annotates cells from single-cell spatial transcriptomics (scST) data. It is a deep learning-based tool that uses a heterogeneous graph neural network to transfer the cell-type labels from single-cell RNA-seq (scRNA-seq) data to scST data. 

We also collected 81 scST datasets consisting of 344 slices and 16 paired scRNA-seq datasets from eight technologies and five tissues, served as a benchmark for scST annotation (can be downloaded from [here](https://drive.google.com/drive/folders/1xP3Fh94AwKu4OsH3khGq-KEw0VCoiRnL)).

![](./STAMapper_overview.png)

## Prerequisites
It is recommended to use a Python version  `3.9`.

## Software dependencies
The important Python packages used to run the model are as follows: 
```
scanpy[leiden]>=1.9.1,<=1.9.5
torch>=1.12.0,<=2.0.1
torchvision>=0.13.0,<=1.15.2
dgl==1.1.2
```
STAMapper is running on GPU, the versions of torch and torchvision 
need to be compatible with the version of CUDA.


## Installation
After downloading STAMapper from [Github](https://github.com/zhanglabtools/STAMapper), 
you can install STAMapper via:

```
cd STAMapper-main
python setup.py build
python setup.py install
```
## Tutorials
The following are detailed tutorials. All tutotials were ran on a 12600kf cpu and a 3060 12G gpu.

1. [Cell-type annotation on scST data (with pre-annoated info)](./Tutorials/Tutorial1 cell-type annotation on scST data (with pre-annoated info).ipynb).

2. [Cell-type annotation on scST data (without pre-annoated info)](./Tutorials/Tutorial2 cell-type annotation on scST data (without pre-annoated info).ipynb).

3. [Localization of human SCC cells on tissue sections](./Tutorials/Tutorial3 reannotation on scST data (with pre-annoated info).ipynb).

4. [Unknown cell type detectio](./Tutorials/Tutorial4 unknown cell type detection.ipynb).

5. [Gene module extraction](./Tutorials/Tutorial5 gene module extraction.ipynb).

