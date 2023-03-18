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
from einops import rearrange


# Set seed for randomize functions (Ez reproduction of results)
random.seed(100)

# Import TuSimple loader
import sys
sys.path.insert(0,'../resources/')
from tusimple import TuSimple


# Linear decoder for the ViT encoder (ViT+Linear Reg Segmenter)
class DecoderLinear(nn.Module):
    def __init__(self, n_classes, d_encoder, patch_size = 16, image_size = (640,640)):
        super().__init__()
        self.image_size = image_size
        self.d_encoder = d_encoder
        self.patch_size = patch_size
        self.n_cls = n_classes

        self.head = nn.Linear(self.d_encoder, n_classes)
        
        self.apply(self.init_weights)

    def forward(self, x):
        H, W = self.image_size
        GS = H // self.patch_size
        x = self.head(x)
        x = rearrange(x, "b (h w) c -> b c h w", h=GS)

        return x
    
    # Init weights method
    @staticmethod
    def init_weights(module):
        if isinstance(module, (nn.Linear, nn.Conv2d)):
            nn.init.kaiming_normal_(module.weight, mode='fan_in')
            if module.bias is not None:
                nn.init.constant_(module.bias, 0)