# STAMapper

## Overview
STAMapper is a method that annotates cells from single-cell spatial transcriptomics (scST) data. It is a deep learning-based tool that uses a heterogeneous graph neural network to transfer the cell-type labels from single-cell RNA-seq (scRNA-seq) data to scST data. 

We also collected 81 scST datasets consisting of 344 slices and 16 paired scRNA-seq datasets from eight technologies and five tissues, served as a benchmark for scST annotation (can be downloaded from [here](https://drive.google.com/drive/u/0/folders/1xP3Fh94AwKu4OsH3khGq-KEw0VCoiRnL)).

![](./STAMapper_overview.png)

## Prerequisites
It is recommended to use a Python version  `3.9`.
* set up conda environment for STAMapper:
```
conda create -n STAMapper python==3.9
```
* install STAMapper from shell:
```
conda activate STAMapper
```

* the important Python packages used to run the model are as follows: 
```
torch>=1.12.0,<=2.0.1
torchvision>=0.13.0,<=0.15.2
dgl>=1.1.2,<=2.1.0
scanpy>=1.9.1
```
STAMapper is test on GPU, the versions of [torch, torchvision](https://pytorch.org/) and [dgl](https://www.dgl.ai/pages/start.html)
need to be compatible with the version of CUDA.


## Installation
You can install STAMapper via:
```
git clone https://github.com/zhanglabtools/STAMapper.git
cd STAMapper
python setup.py build
python setup.py install
```

## Tutorials
The following are detailed tutorials. All tutorials were ran on a 12600kf cpu and a 3060 12G gpu.

1. [Cell-type annotation on scST data (with pre-annotated info)](./Tutorials/Tutorial1_cell-type_annotation_on_scST_data_(with_pre-annotated_info).ipynb).

2. [Cell-type annotation on scST data (without pre-annotated info)](./Tutorials/Tutorial2_cell-type_annotation_on_scST_data_(without_pre-annotated_info).ipynb).

3. [Reannotation on scST data (with pre-annotated info)](./Tutorials/Tutorial3_reannotation_on_scST_data_(with_pre-annotated_info).ipynb).

4. [Unknown cell type detection](./Tutorials/Tutorial4_unknown_cell_type_detection.ipynb).

5. [Gene module extraction](./Tutorials/Tutorial5_gene_module_extraction.ipynb).
