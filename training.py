import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
import matplotlib.pyplot as plt
import glob
import warnings

from torch.utils.data.sampler import SubsetRandomSampler
from pathlib import Path
from dataset import ActionsDataset
from model import TCNN as Net
from collections import defaultdict

warnings.filterwarnings('ignore')


if __name__ == "__main__":
    
    DATA = Path('data')

    data_map = defaultdict(dict)

    for cat in DATA.iterdir():
        for batch in Path(cat).iterdir():
            images = glob.glob(str(batch)+'/*.jpg')
            captions = glob.glob(str(batch)+'/gt/*.txt')
            if data_map.get(str(cat)) is None:
                data_map[str(cat)]['images'] = sorted(images)
                data_map[str(cat)]['captions'] = sorted(captions)
            else:
                data_map[str(cat)]['images'] = data_map[str(cat)]['images']+sorted(images)
                data_map[str(cat)]['captions'] = data_map[str(cat)]['captions']+sorted(captions)
            
    input_size = (300, 300, 3)
    seed = 38

    net = Net(input_size, seed)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.SGD(net.parameters(), lr=0.001, momentum=0.9)

    dataset = ActionsDataset(data_map)
    
    batch_size = 8
    validation_split = .2
    shuffle_dataset = True
    random_seed= 38

    # Creating data indices for training and validation splits:
    dataset_size = len(dataset)
    indices = list(range(dataset_size))
    split = int(np.floor(validation_split * dataset_size))
    if shuffle_dataset :
        np.random.seed(random_seed)
        np.random.shuffle(indices)
    train_indices, val_indices = indices[split:], indices[:split]

    train_sampler = SubsetRandomSampler(train_indices)
    valid_sampler = SubsetRandomSampler(val_indices)

    train_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, 
                                               sampler=train_sampler)
    validation_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size,
                                                    sampler=valid_sampler)    

    EPOCHS = 10

    for epoch in range(EPOCHS):

        running_loss = 0.0
        for batch_index, (images, bboxs) in enumerate(train_loader):
            
            optimizer.zero_grad()
            out = net(images)

            loss = criterion(out, bboxs)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

            if i%2000 == 1999:
                print('[%d, %5d] loss: %.3f' %
                         (epoch + 1, i+1, running_loss / 2000))
                running_loss = 0.0