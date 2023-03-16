# Imports 
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import random
import cv2
import os
import json
import math
import torch.nn.init as init
import torch.optim as optim
from torch.utils.data import DataLoader
from torchmetrics import F1Score,JaccardIndex

# Set seed for randomize functions (Ez reproduction of results)
random.seed(100)

# Import TuSimple loader
import sys
sys.path.insert(0,'../resources/')
from tusimple import TuSimple
from mask_transformer import MaskTransformer
from vit import ViT
import utils


# Custom training function for the transformer pipeline with schedule and SGD optimizer
def train(model, train_loader, val_loader = None, num_epochs=10, lr=0.01, momentum=0.9, weight_decay=1e-4, lr_scheduler=True):
    # Set up loss function and optimizer
    criterion =  nn.BCEWithLogitsLoss()
    optimizer = optim.SGD(model.parameters(), lr=lr, momentum=momentum, weight_decay=weight_decay)

    # Set up learning rate scheduler
    if lr_scheduler:
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

    # Set up device (GPU or CPU)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    f1_score = F1Score(task="binary")
    iou_score = JaccardIndex(task= 'binary')

    # Train the model
    for epoch in range(num_epochs):
        train_loss = 0
        train_acc = 0
        train_iou = 0
        train_f1 = 0
        
        val_acc = 0
        val_iou = 0
        val_f1 = 0
        
        for batch_idx, (inputs, targets) in enumerate(train_loader):
            model.train()
            inputs, targets = inputs.to(device), targets.to(device)
                   
            optimizer.zero_grad()
            outputs = model(inputs)
            outputs.requires_grad = True
            
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            
            train_loss += loss.item() * inputs.size(0)
            train_acc += utils.accuracy(pred = outputs.detach(), target = targets)
            train_iou += iou_score(outputs.detach(), targets)
            train_f1 += f1_score(outputs.detach(), targets)
            
        if val_loader:
            for batch_idx, (inputs, targets) in enumerate(train_loader): 
                model.eval()
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                
                val_acc += utils.accuracy(pred = outputs.detach(), target = targets)
                val_iou += iou_score(outputs, targets)
                val_f1 += f1_score(outputs,targets)
        
            val_acc /= len(val_loader)
            val_iou /= len(val_loader)
            val_f1 /= len(val_loader)
            
        train_loss /= len(train_loader)
        train_acc /= len(train_loader)
        train_iou /= len(train_loader)
        train_f1 /= len(train_loader)
        
        
        
     # Print progress
        if lr_scheduler:
            print('Epoch: {} - Train Loss: {:.4f} - Learning Rate: {:.6f} - Train_Acc: {:.3f} - Train_IoU: {:.3f} - Train_F1: {:.3f}'.format(epoch+1, train_loss,scheduler.get_last_lr()[0],train_acc, train_iou, train_f1))
            scheduler.step()
            if val_loader:
                print('Val_Acc: {:.3f}  - Val_F1: {:.3f}  - Val_IoU: {:.3f} '.format(val_acc,val_f1,val_iou))
        else:
            print('Epoch: {} - Train Loss: {:.4f}'.format(epoch+1, train_loss))
            
            
# Segmenter pipeline class (ViT + Masks transformer end-to-end)
class Segmenter(nn.Module):
    def __init__(self,encoder, mask_trans, image_size = (640,640)):
        super().__init__()
        self.patch_size = encoder.patch_size
        self.encoder = encoder
        self.decoder = mask_trans
        self.image_size = image_size
        
    # Forward pass of the pipeline
    def forward(self, im):
        H, W = self.image_size
        
        # Pass through the pre-trained vit backbone
        x = self.encoder(im, return_features=True)
        
        # Pass through the masks transformer
        masks = self.decoder(x)

        # Interpolate patch level class annotatations to pixel level and transform to original image size
        masks = F.interpolate(masks, size=(H, W), mode="bilinear")
        predicted_masks = torch.argmax(masks, dim=1).float()
        
        # expand the output mask tensor along the channel dimension to match the ground truth tensor (maybe needs removal)
        predicted_masks = predicted_masks.unsqueeze(0).expand(3, -1, -1, -1).transpose(0, 1).squeeze(0)

        return predicted_masks
    
    # Count pipeline trainable parameters
    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
