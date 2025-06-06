import torch
import torch.nn as nn
from torch.nn import init
import torch.nn.functional as F
###############################################################################
# Functions
###############################################################################


def init_weights_r2u(net, init_type='normal', gain=0.02):
    def init_func(m):
        classname = m.__class__.__name__
        if hasattr(m, 'weight') and (classname.find('Conv') != -1 or classname.find('Linear') != -1):
            if init_type == 'normal':
                init.normal_(m.weight.data, 0.0, gain)
            elif init_type == 'xavier':
                init.xavier_normal_(m.weight.data, gain=gain)
            elif init_type == 'kaiming':
                init.kaiming_normal_(m.weight.data, a=0, mode='fan_in')
            elif init_type == 'orthogonal':
                init.orthogonal_(m.weight.data, gain=gain)
            else:
                raise NotImplementedError('initialization method [%s] is not implemented' % init_type)
            if hasattr(m, 'bias') and m.bias is not None:
                init.constant_(m.bias.data, 0.0)
        elif classname.find('BatchNorm2d') != -1:
            init.normal_(m.weight.data, 1.0, gain)
            init.constant_(m.bias.data, 0.0)

    print('initialize network with %s' % init_type)
    net.apply(init_func)

class conv_block_r2u(nn.Module):
    def __init__(self,ch_in,ch_out):
        super(conv_block_r2u,self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(ch_in, ch_out, kernel_size=3,stride=1,padding=1,bias=True),
            nn.BatchNorm2d(ch_out),
            nn.ReLU(inplace=True),
            nn.Conv2d(ch_out, ch_out, kernel_size=3,stride=1,padding=1,bias=True),
            nn.BatchNorm2d(ch_out),
            nn.ReLU(inplace=True)
        )


    def forward(self,x):
        x = self.conv(x)
        return x

class up_conv_r2u(nn.Module):
    def __init__(self,ch_in,ch_out):
        super(up_conv_r2u,self).__init__()
        self.up = nn.Sequential(
            nn.Upsample(scale_factor=2),
            nn.Conv2d(ch_in,ch_out,kernel_size=3,stride=1,padding=1,bias=True),
		    nn.BatchNorm2d(ch_out),
			nn.ReLU(inplace=True)
        )

    def forward(self,x):
        x = self.up(x)
        return x

class Recurrent_block_r2u(nn.Module):
    def __init__(self,ch_out,t=2):
        super(Recurrent_block_r2u,self).__init__()
        self.t = t
        self.ch_out = ch_out
        self.conv = nn.Sequential(
            nn.Conv2d(ch_out,ch_out,kernel_size=3,stride=1,padding=1,bias=True),
		    nn.BatchNorm2d(ch_out),
			nn.ReLU(inplace=True)
        )

    def forward(self,x):
        for i in range(self.t):

            if i==0:
                x1 = self.conv(x)
            
            x1 = self.conv(x+x1)
        return x1
        
# class RRCNN_block_r2u(nn.Module):
#     def __init__(self,ch_in,ch_out,t=2):
#         super(RRCNN_block_r2u,self).__init__()
#         self.RCNN = nn.Sequential(
#             Recurrent_block_r2u(ch_out,t=t),
#             Recurrent_block_r2u(ch_out,t=t)
#         )
#         self.Conv_1x1 = nn.Conv2d(ch_in,ch_out,kernel_size=1,stride=1,padding=0)

#     def forward(self,x):
#         x = self.Conv_1x1(x)
#         x1 = self.RCNN(x)
#         return x+x1

class RRCNN_block_r2u(nn.Module):
    def __init__(self,ch_in,ch_out,t=2):
        super(RRCNN_block_r2u,self).__init__()
        self.RCNN = nn.Sequential(
            Recurrent_block_r2u(ch_out, t=t),
            Recurrent_block_r2u(ch_out, t=t)
        )
        self.Conv = nn.Sequential(
                nn.Conv2d(ch_in, ch_out, kernel_size=1, stride=1, padding=0),
                nn.BatchNorm2d(ch_out),
                nn.ReLU(inplace=True)
        )
        self.activate = nn.ReLU(inplace=True)
        # self.Conv = nn.Conv2d(in_ch, out_ch, kernel_size=1, stride=1, padding=0)
        
    def forward(self, x):
        x1 = self.Conv(x)
        x2 = self.RCNN(x1)
        out = self.activate(x1 + x2)
        return out



class single_conv_r2u(nn.Module):
    def __init__(self,ch_in,ch_out):
        super(single_conv_r2u,self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(ch_in, ch_out, kernel_size=3,stride=1,padding=1,bias=True),
            nn.BatchNorm2d(ch_out),
            nn.ReLU(inplace=True)
        )

    def forward(self,x):
        x = self.conv(x)
        return x

class Attention_block_r2u(nn.Module):
    def __init__(self,F_g,F_l,F_int):
        super(Attention_block_r2u,self).__init__()
        self.W_g = nn.Sequential(
            nn.Conv2d(F_g, F_int, kernel_size=1,stride=1,padding=0,bias=True),
            nn.BatchNorm2d(F_int)
            )
        
        self.W_x = nn.Sequential(
            nn.Conv2d(F_l, F_int, kernel_size=1,stride=1,padding=0,bias=True),
            nn.BatchNorm2d(F_int)
        )

        self.psi = nn.Sequential(
            nn.Conv2d(F_int, 1, kernel_size=1,stride=1,padding=0,bias=True),
            nn.BatchNorm2d(1),
            nn.Sigmoid()
        )
        
        self.relu = nn.ReLU(inplace=True)
        
    def forward(self,g,x):
        g1 = self.W_g(g)
        x1 = self.W_x(x)
        psi = self.relu(g1+x1)
        psi = self.psi(psi)

        return x*psi





from Networks.DP_CoNet import EPEDLayer

class R2U_Net_EPED(nn.Module):
    def __init__(self,img_ch=3,output_ch=1,t=3):
        super(R2U_Net_EPED,self).__init__()
        
        self.Maxpool = nn.MaxPool2d(kernel_size=2,stride=2)
        self.Upsample = nn.Upsample(scale_factor=2)

        self.RRCNN1 = RRCNN_block_r2u(ch_in=img_ch,ch_out=32,t=t)

        self.RRCNN2 = RRCNN_block_r2u(ch_in=32,ch_out=64,t=t)
        
        self.RRCNN3 = RRCNN_block_r2u(ch_in=64,ch_out=128,t=t)
        
        self.RRCNN4 = RRCNN_block_r2u(ch_in=128,ch_out=256,t=t)
        
        self.RRCNN5 = RRCNN_block_r2u(ch_in=256,ch_out=512,t=t)
        

        self.Up5 = up_conv_r2u(ch_in=512,ch_out=256)
        self.Up_RRCNN5 = RRCNN_block_r2u(ch_in=512, ch_out=256,t=t)
        
        self.Up4 = up_conv_r2u(ch_in=256,ch_out=128)
        self.Up_RRCNN4 = RRCNN_block_r2u(ch_in=256, ch_out=128,t=t)
        00
        self.Up3 = up_conv_r2u(ch_in=128,ch_out=64)
        self.Up_RRCNN3 = RRCNN_block_r2u(ch_in=128, ch_out=64,t=t)
        
        self.Up2 = up_conv_r2u(ch_in=64,ch_out=32)
        self.Up_RRCNN2 = RRCNN_block_r2u(ch_in=64, ch_out=32,t=t)

        self.Conv_1x1 = nn.Conv2d(32,output_ch,kernel_size=1,stride=1,padding=0)
         # 添加softmax层
        self.softmax = nn.Softmax(dim=1)  

        self.eped64=EPEDLayer(64)
        self.eped128=EPEDLayer(128)
        self.eped256=EPEDLayer(256)
        self.eped512=EPEDLayer(512)
        self.eped1024=EPEDLayer(1024)  

    def forward(self,x):
        # encoding path
        x1 = self.RRCNN1(x)
        
        x2 = self.Maxpool(x1)
        x2 = self.RRCNN2(x2)
        x2=self.eped64(x2)

        x3 = self.Maxpool(x2)
        x3 = self.RRCNN3(x3)
        x3=self.eped128(x3)

        x4 = self.Maxpool(x3)
        x4 = self.RRCNN4(x4)
        x4=self.eped256(x4)

        x5 = self.Maxpool(x4)
        x5 = self.RRCNN5(x5)
        x5=self.eped512(x5)

        # decoding + concat path
        d5 = self.Up5(x5)
        d5 = torch.cat((x4,d5),dim=1)
        d5 = self.Up_RRCNN5(d5)
        
        d4 = self.Up4(d5)
        d4 = torch.cat((x3,d4),dim=1)
        d4 = self.Up_RRCNN4(d4)

        d3 = self.Up3(d4)
        d3 = torch.cat((x2,d3),dim=1)
        d3 = self.Up_RRCNN3(d3)

        d2 = self.Up2(d3)
        d2 = torch.cat((x1,d2),dim=1)
        d2 = self.Up_RRCNN2(d2)

        d1 = self.Conv_1x1(d2)
        # d1 = self.softmax(d1)   # 添加softmax操作

        return d1
