import torch
import torch.nn as nn
import torch.nn.functional as F


class _MaxPoolNd(nn.Module):
    __constants__ = ['kernel_size', 'stride', 'padding', 'dilation',
                     'return_indices', 'ceil_mode']

    def __init__(self, kernel_size, stride=None, padding=0, dilation=1,
                 return_indices=False, ceil_mode=False):
        super(_MaxPoolNd, self).__init__()
        self.kernel_size = kernel_size
        self.stride = stride or kernel_size
        self.padding = padding
        self.dilation = dilation
        self.return_indices = return_indices
        self.ceil_mode = ceil_mode

    def extra_repr(self):
        return 'kernel_size={kernel_size}, stride={stride}, padding={padding}' \
            ', dilation={dilation}, ceil_mode={ceil_mode}'.format(**self.__dict__)


class Linker:
    def __init__(self, n_clips=8):
        self.n_clips = n_clips

    def link_proposals(self, tube_proposals):
        prop_seq = []
        overlap = 0
        for i in range(len(tube_proposals)):
            overlap += self.count_overlap(tube_proposals[i], tube_proposals[i+1])
        return prop_seq

    @staticmethod
    def count_overlap(tp1, tp2):
        """
            Computes IoU between last and first frames
            in corresponding sibling proposals
        """
        overlap = 0

        return overlap

    @staticmethod
    def count_actionness(actionness):
        acts = torch.sum(actionness, dim=0)
        return acts

    def compute_score(self, acts, overlap):
        score = 1/self.n_clips*acts+1/(self.n_clips-1)*overlap
        return score


class ToiPool(_MaxPoolNd):
    def __init__(self, kernel_size, d, h, w):
        super(ToiPool, self).__init__(kernel_size)
        self.D = d
        self.height = h
        self.width = w

    def forward(self, frame):
        return F.max_pool2d(frame, self.kernel_size, self.stride,
                            self.padding, self.dilation, self.ceil_mode,
                            self.return_indices)


class TPN(nn.Module):
    def __init__(self, input_C, fc6_units=8192, fc7_units=4096, fc8_units=4096):
        """Initialize parameters and build model.
        Params
        ======
            fc6_units (int): Number of nodes in first hidden layer
            fc7_units (int): Number of nodes in second hidden layer
        """
        super(TPN, self).__init__()
        self.in_channels = input_C  # output feature map
        self.n_anchor = 9  # no. of anchors at each location
        self.toi2 = ToiPool(3, 8, 8, 8)
        self.toi5 = ToiPool(3, 1, 4, 4)
        self.conv11 = nn.Conv1d(512, 8192, 1)
        self.fc6 = nn.Linear(fc6_units, fc7_units)
        self.fc7 = nn.Linear(fc7_units, fc8_units)
        self.fc7 = nn.Linear(fc8_units, fc8_units)

    def forward(self, reg, conv2):
        x1 = self.toi2(conv2)
        x1 = torch.norm(x1, p=None)
        x2 = self.toi5(reg)
        x2 = torch.norm(x2, p=None)
        x = torch.cat((x1, x2), dim=0)
        reg = self.conv11(x)
        clf = self.conv11(x)
        reg = self.fc6(reg)
        reg = self.fc7(reg)
        return reg


class TCNN(nn.Module):
    """End-to-end action detection model"""

    def __init__(self, input_size, seed, fc8_units=4096):
        """Initialize parameters and build model.
        Params
        ======
            seed (int): Random seed
        """
        super(TCNN, self).__init__()
        self.seed = torch.manual_seed(seed)
        self.n_anchor = 9  # no. of anchors at each location
        self.conv1 = nn.Conv3d(input_size, 64, (3, 3, 3), padding=1)
        self.pool1 = nn.MaxPool3d((1, 2, 2))
        self.conv2 = nn.Conv3d(64, 128, (3, 3, 3), padding=1)
        self.pool2 = nn.MaxPool3d((2, 2, 2))
        self.conv3a = nn.Conv3d(128, 256, (3, 3, 3), padding=1)
        self.conv3b = nn.Conv3d(256, 256, (3, 3, 3), padding=1)
        self.pool3 = nn.MaxPool3d((2, 2, 2))
        self.conv4a = nn.Conv3d(256, 512, (3, 3, 3), padding=1)
        self.conv4b = nn.Conv3d(512, 512, (3, 3, 3), padding=1)
        self.pool4 = nn.MaxPool3d((2, 2, 2))
        self.conv5a = nn.Conv3d(512, 512, (3, 3, 3), padding=1)
        self.conv5b = nn.Conv3d(512, 512, (3, 3, 3), padding=1)
        self.TPN = TPN(512)
        self.reg_layer = nn.Conv3d(fc8_units, self.n_anchor * 4, 1, 1, 0)
        self.cls_layer = nn.Conv3d(fc8_units, self.n_anchor * 2, 1, 1, 0)

    def forward(self, x):
        """Build a network that maps anchor boxes to a seq. of frames."""
        x = self.pool1(F.leaky_relu(self.conv1(x)))
        x = self.pool2(F.leaky_relu(self.conv2(x)))
        x = self.pool3(F.leaky_relu(
            self.conv3b(F.leaky_relu(self.conv3a(x)))))
        x = self.pool4(F.leaky_relu(
            self.conv4b(F.leaky_relu(self.conv4a(x)))))
        x = F.leaky_relu(self.conv5b(F.leaky_relu(self.conv5a(x))))
        reg = self.reg_layer(x)
        clf = self.cls_layer(x)
        ref_reg = self.TPN(reg, self.conv2)  # proposed tubes

        return x