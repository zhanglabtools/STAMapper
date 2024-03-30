# -*- coding: utf-8 -*-
"""
Created on Mon Oct 11 10:36:09 2023

@author: Qunlun Shen
"""
import logging
from pathlib import Path
import os
from typing import Sequence, Union, Mapping, Optional, List
import torch.nn as nn
import time
import random
import numpy as np
from pandas import value_counts
import torch
from torch import Tensor, LongTensor
import dgl
import tqdm
from ..datapair.aligned import AlignedDataPair
from ..datapair.unaligned import DataPair

from ..model import (
    to_device, onehot_encode, idx_hetero, infer_classes,
    multilabel_binary_cross_entropy,
    cross_entropy_loss,
    ce_loss_with_rdrop,
    classification_loss,
    Neg_Pearson_Loss
)
from ..model._minibatch import create_batch, create_blocks
from .evaluation import accuracy, get_AMI, get_F1_score, detach2numpy
from .plot import plot_records_for_trainer
from ._base_trainer import BaseTrainer, SUBDIR_MODEL

B = shuffle = False


def seed_everything(seed=123):
    """ not works well """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    dgl.random.seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    
    

def make_class_weights(labels, astensor=True, foo=np.sqrt, n_add=0):
    if isinstance(labels, Tensor):
        labels = labels.cpu().clone().detach().numpy()

    counts = value_counts(labels).sort_index()  # sort for alignment
    n_cls = len(counts) + n_add
    w = counts.apply(lambda x: 1 / foo(x + 1) if x > 0 else 0)  
    w = (w / w.sum() * (1 - n_add / n_cls)).values
    w = np.array(list(w) + [1 / n_cls] * int(n_add))

    if astensor:
        return Tensor(w)
    return w



def sub_graph(cell_ID, gene_ID, g):
    """
    Making sub_graph for g with input cell_ID and gene_ID
    """
    output_nodes_dict = {'cell': cell_ID, 'gene': gene_ID}
    g_subgraph = dgl.node_subgraph(g, output_nodes_dict)
    return g_subgraph


def create_blocks(g, output_nodes):
    cell_ID = output_nodes.clone().detach()
    gene_ID = g.in_edges(cell_ID, etype='expressed_by')[0]  # genes expressed_by cells
    gene_ID = torch.unique(gene_ID)
    block = sub_graph(cell_ID, gene_ID, g)  # graph for GAT
    return block


def create_batch(sample_size=None, train_idx=None, test_idx=None, batchsize=None, labels=None, shuffle=True,
                 label=True):
    """
    This function create batch idx, i.e. the cells IDs in a batch.
    ----------------------------------------------------------------------
    Parameters
    -----------
    train_idx: the index for reference cells
    test_idx: the index for query cells
    batchsize: the number of cells in each batch
    labels: the labels for both Reference cells and Query cells
    ----------------------------------------------------------------------
    Returns
    -----------
    train_labels: the shuffled or non-shuffled labels for all reference cells
    test_labels: the shuffled or non-shuffled labels for all query cells
    batch_list: the list sores the batch of cell IDs
    all_idx: the shuffled or non-shuffled index for all cells
    ----------------------------------------------------------------------
    """
    if label:
        batch_list = []
        batch_labels = []
        sample_size = len(train_idx) + len(test_idx)
        if shuffle:
            all_idx = torch.randperm(sample_size)
            shuffled_labels = labels[all_idx]
            train_labels = shuffled_labels[all_idx < len(train_idx)].clone().detach()
            test_labels = shuffled_labels[all_idx >= len(train_idx)].clone().detach()

            if batchsize >= sample_size:
                batch_list.append(all_idx)

            else:
                batch_num = int(len(all_idx) / batchsize) + 1
                for i in range(batch_num - 1):
                    batch_list.append(all_idx[batchsize * i: batchsize * (i + 1)])
                batch_list.append(all_idx[batchsize * (batch_num - 1):])

        else:
            train_labels = labels[train_idx].clone().detach()
            test_labels = labels[test_idx].clone().detach()
            all_idx = torch.cat((train_idx, test_idx), 0)
            if batchsize >= sample_size:
                batch_list.append(all_idx)
            else:
                batch_num = int(len(all_idx) / batchsize) + 1
                for i in range(batch_num - 1):
                    batch_list.append(all_idx[batchsize * i: batchsize * (i + 1)])
                    batch_labels.append(labels[batchsize * i: batchsize * (i + 1)])
                batch_list.append(all_idx[batchsize * (batch_num - 1):])

        return train_labels, test_labels, batch_list, all_idx

    else:
        batch_list = []
        if shuffle:
            all_idx = torch.randperm(sample_size)

            if batchsize >= sample_size:
                batch_list.append(all_idx)
            else:
                batch_num = int(len(all_idx) / batchsize) + 1
                for i in range(batch_num - 1):
                    batch_list.append(all_idx[batchsize * i: batchsize * (i + 1)])
                batch_list.append(all_idx[batchsize * (batch_num - 1):])

        else:
            all_idx = torch.arange(sample_size)
            if batchsize >= sample_size:
                batch_list.append(all_idx)
            else:
                batch_num = int(len(all_idx) / batchsize) + 1
                for i in range(batch_num - 1):
                    batch_list.append(all_idx[batchsize * i: batchsize * (i + 1)])
                batch_list.append(all_idx[batchsize * (batch_num - 1):])

        return batch_list, all_idx


class BatchTrainer(BaseTrainer):
    """


    """

    def __init__(self,
                 model,
                 feat_dict: Mapping,
                 g: dgl.DGLGraph,
                 train_idx: Tensor,
                 test_idx: Tensor,
                 train_labels: Tensor,
                 test_labels: Optional[Tensor] = None,
                 cluster_labels: Union[None, Sequence, Tensor] = None,
                 lr=1e-3,
                 l2norm=1e-2,  # 1e-2 is tested for all datasets
                 use_cuda=True,
                 dir_main=Path('.'),
                 **kwds  # for code compatibility (not raising error)
                 ):
        super(BatchTrainer, self).__init__(
            model,
            feat_dict=feat_dict,
            train_labels=train_labels,
            test_labels=test_labels,
            train_idx=train_idx,
            test_idx=test_idx,
            cluster_labels=cluster_labels,
            lr=lr,
            l2norm=l2norm,  # 1e-2 is tested for all datasets
            use_cuda=use_cuda,
            dir_main=dir_main,
            **kwds  # for code compatibility (not raising error)
        )
        self.g = g.to(self.device)
        self.set_class_weights()  # class weights
        ### infer n_classes
        self.n_classes = len(self.class_weights)

        _record_names = (
            'dur',
            'train_loss',
            'test_loss',
            'train_acc',
            'test_acc',
            'AMI',
            'microF1',
            'macroF1',
            'weightedF1',
        )
        self.set_recorder(*_record_names)

    def set_class_weights(self, class_weights=None, foo=np.sqrt, n_add=0):
        if class_weights is None:
            self.class_weights = make_class_weights(
                self.train_labels, foo=foo, n_add=n_add)
        else:
            self.class_weights = Tensor(class_weights)

    def plot_class_losses(self, start=0, end=None, fp=None):
        plot_records_for_trainer(
            self,
            record_names=['train_loss', 'test_loss'],
            start=start, end=end,
            lbs=['training loss', 'testing loss'],
            tt='classification losses',
            fp=fp)

    def plot_class_accs(self, start=0, end=None, fp=None):
        plot_records_for_trainer(
            self,
            record_names=['train_acc', 'test_acc'],
            start=start, end=end,
            lbs=['training acc', 'testing acc'],
            tt='classification accuracy',
            fp=fp)

    def plot_cluster_index(self, start=0, end=None, fp=None):
        plot_records_for_trainer(
            self,
            record_names=['test_acc', 'AMI'],
            start=start, end=end,
            lbs=['test accuracy', 'AMI'],
            tt='test accuracy and cluster index',
            fp=fp)

    def train_minibatch(self, n_epochs=100,
                        use_class_weights=True,
                        params_lossfunc={},
                        n_pass=100,
                        eps=1e-4,
                        cat_class='cell',
                        batchsize=128,
                        device=None,
                        **other_inputs):
        """
        Funtcion for minibatch trainging
        """
        # setting device to train
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'

        train_idx, test_idx, train_labels, test_labels = self.train_idx, self.test_idx, self.train_labels, self.test_labels
        labels = torch.cat((train_labels, test_labels), 0)
        self.g.nodes['cell'].data['ids'] = torch.arange(self.g.num_nodes('cell'))  # track the random shuffle

        if use_class_weights:
            class_weights = self.class_weights

        if not hasattr(self, 'ami_max'):
            self.ami_max = 0

        print("start training".center(50, '='))
        self.model.train()
        self.model = self.model.to(device)
        feat_dict = {}
        train_labels, test_labels, batch_list, shuffled_idx = create_batch(
            train_idx=train_idx, test_idx=test_idx, batchsize=batchsize,
            labels=labels, shuffle=True)
        shuffled_test_idx = detach2numpy(
            shuffled_idx[shuffled_idx >= len(train_idx)]
        ) - len(train_idx)
        cluster_labels = self.cluster_labels[shuffled_test_idx]
        blocks = []
        for output_nodes in tqdm.tqdm(batch_list):
            block = create_blocks(g=self.g, output_nodes=output_nodes)
            blocks.append(block)

        for epoch in range(n_epochs):
            self._cur_epoch += 1
            self.optimizer.zero_grad()
            all_train_preds = to_device(torch.tensor([]), device)
            all_test_preds = to_device(torch.tensor([]), device)
            t0 = time.time()
            batch_rank = 0
            for output_nodes in tqdm.tqdm(batch_list):
                block = blocks[batch_rank]
                batch_rank += 1
                feat_dict['cell'] = self.feat_dict['cell'][block.nodes['cell'].data['ids'], :]
                batch_train_idx = output_nodes.clone().detach() < len(train_idx)
                batch_test_idx = output_nodes.clone().detach() >= len(train_idx)
                logits = self.model(to_device(feat_dict, device),
                                    to_device(block, device),
                                    **other_inputs)
                out_cell = logits[cat_class]  # .cuda()
                output_labels = labels[output_nodes]
                out_train_labels = output_labels[batch_train_idx].clone().detach()
                loss = self.model.get_classification_loss(
                    out_cell[batch_train_idx],
                    to_device(out_train_labels, device),
                    weight=to_device(class_weights, device),
                    **params_lossfunc
                )
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                _, y_pred = torch.max(out_cell, dim=1)
                y_pred_train = y_pred[batch_train_idx]
                y_pred_test = y_pred[batch_test_idx]
                all_train_preds = torch.cat((all_train_preds, y_pred_train), 0)
                all_test_preds = torch.cat((all_test_preds, y_pred_test), 0)

            # evaluation (Acc.)
            all_train_preds = all_train_preds.cpu()
            all_test_preds = all_test_preds.cpu()
            with torch.no_grad():
                train_acc = accuracy(train_labels, all_train_preds)
                test_acc = accuracy(test_labels, all_test_preds)
                # F1-scores
                microF1 = get_F1_score(test_labels, all_test_preds, average='micro')
                macroF1 = get_F1_score(test_labels, all_test_preds, average='macro')
                weightedF1 = get_F1_score(test_labels, all_test_preds, average='weighted')

                # unsupervised cluster index
                if self.cluster_labels is not None:
                    ami = get_AMI(cluster_labels, all_test_preds)

                if self._cur_epoch >= n_pass - 1:
                    self.ami_max = max(self.ami_max, ami)
                    if ami > self.ami_max - eps:
                        self._cur_epoch_best = self._cur_epoch
                        self.save_model_weights()
                        print('[current best] model weights backup')
                    elif self._cur_epoch % 43 == 0:
                        self.save_model_weights()
                        print('model weights backup')

                t1 = time.time()

                # recording
                self._record(dur=t1 - t0,
                             train_loss=loss.item(),
                             train_acc=train_acc,
                             test_acc=test_acc,
                             AMI=ami,
                             microF1=microF1,
                             macroF1=macroF1,
                             weightedF1=weightedF1,
                             )

                dur_avg = np.average(self.dur)
                test_acc_max = max(self.test_acc)
                logfmt = "Epoch {:05d} | Train Acc: {:.4f} | Test Acc: {:.4f} (max={:.4f}) | AMI={:.4f} | Time: {:.4f}"
                self._cur_log = logfmt.format(
                    self._cur_epoch, train_acc,
                    test_acc, test_acc_max,
                    ami, dur_avg)

                print(self._cur_log)
            self._cur_epoch_adopted = self._cur_epoch

    def eval_current(self,
                     feat_dict=None,
                     g=None,
                     device=None,
                     **other_inputs):
        """ get the current states of the model output
        """
        print('eval_current')
        if feat_dict is None:
            feat_dict = self.feat_dict
        if g is None:
            g = self.g
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        feat_dict = to_device(feat_dict, device)
        g = g.to(device)
        with torch.no_grad():
            self.model.train()  # semi-supervised learning
            # self.model.eval()
            output = self.model.forward(
                feat_dict, g,  # .to(self.device),
                **other_inputs)
        return output

    def eval_current_batch(self,
                           feat_dict=None,
                           g=None,
                           device=None,
                           batch_size=None,
                           **other_inputs):
        """ get the current states of the model output
        """
        print('eval_current')
        if g is None:
            g = self.g
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        # feat_dict = to_device(feat_dict, device)
        # g = g.to(device)
        output = {}
        feat_dict = {}
        batch_list, all_idx = create_batch(sample_size=self.feat_dict['cell'].shape[0], batchsize=batch_size,
                                           label=False)
        flag = 0
        for output_nodes in tqdm.tqdm(batch_list):
            with torch.no_grad():
                self.model.train()  # semi-supervised learning
                # self.model.eval()
                block = create_blocks(g=self.g, output_nodes=output_nodes)
                feat_dict['cell'] = self.feat_dict['cell'][block.nodes['cell'].data['ids'], :]
                output1 = self.model.forward(to_device(feat_dict, device),
                                             to_device(block, device),
                                             **other_inputs)
                if flag == 0:
                    output['cell'] = output1['cell']
                    flag += 1
                else:
                    output['cell'] = torch.cat((output['cell'], output1['cell']), dim=0)
        return output