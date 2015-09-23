"""
NTM with feed-forward controller, using autodiff
"""
import autograd.numpy as np
from autograd import grad
from util import rando, sigmoid, softmax, softplus
import memory
import addressing
import sys

class NTM(object):

  def __init__(self, in_size, out_size, hidden_size, N, M):

    # TODO: abstract so that we can have multiple gates of both types 
    self.N = N  # the number of memory locations
    self.M = M # the number of columns in a memory location
    self.out_size = out_size

    self.Wxh = rando(hidden_size, in_size) 
    self.Wrh = rando(hidden_size, self.M)
    self.Who = rando(hidden_size, hidden_size)
    self.Woy = rando(out_size, hidden_size)

    self.Wok_r = rando(self.M,hidden_size)
    self.Wok_w = rando(self.M,hidden_size)

    self.Wobeta_r = rando(1,hidden_size)
    self.Wobeta_w = rando(1,hidden_size)

    # the interpolation gate is a scalar, but it doesn't have to be
    # TODO: try having a per_spot interpolation gate
    self.Wog_r = rando(1,hidden_size)
    self.Wog_w = rando(1,hidden_size)

    shift_width = min(3,self.N)
    #shift_width = self.N
    self.Wos_r = rando(shift_width,hidden_size)
    self.Wos_w = rando(shift_width,hidden_size)

    # gamma is also a scalar
    self.Wogamma_r = rando(1,hidden_size)
    self.Wogamma_w = rando(1,hidden_size)

    self.Woadds   = rando(self.M,hidden_size)
    self.Woerases = rando(self.M,hidden_size)

    self.bh  = rando(hidden_size, 1) 
    self.by  = rando(out_size, 1) 
    self.bo  = rando(hidden_size, 1) 

    self.bk_r = rando(self.M,1)
    self.bk_w = rando(self.M,1)

    self.bbeta_r = rando(1,1)
    self.bbeta_w = rando(1,1)

    self.bg_r = rando(1,1)
    self.bg_w = rando(1,1)

    self.bs_r = rando(shift_width,1)
    self.bs_w = rando(shift_width,1)

    self.bgamma_r = rando(1,1)
    self.bgamma_w = rando(1,1)

    self.badds  = rando(self.M,1)
    self.berases = rando(self.M,1)

    # initialize some recurrent things to bias values
    self.rsInit = np.random.uniform(-1,1,(self.M,1)) # we want this to be 8 by 1
    self.memsInit = np.random.randn(self.N,self.M)*0.01
    self.w_ws_initInit = np.random.randn(self.N,1)*0.01
    self.w_rs_initInit = np.random.randn(self.N,1)*0.01

    # TODO: make sure these are up to date
    self.weights = [   self.Wxh
                     , self.Wrh
                     , self.Who
                     , self.Woy
                     , self.Wok_r
                     , self.Wok_w
                     , self.Wobeta_r
                     , self.Wobeta_w
                     , self.Wog_r
                     , self.Wog_w
                     , self.Wos_r
                     , self.Wos_w
                     , self.Wogamma_r
                     , self.Wogamma_w
                     , self.Woadds
                     , self.Woerases
                     , self.bh
                     , self.by
                     , self.bo
                     , self.bk_r
                     , self.bk_w
                     , self.bbeta_r
                     , self.bbeta_w
                     , self.bg_r
                     , self.bg_w
                     , self.bs_r
                     , self.bs_w
                     , self.bgamma_r
                     , self.bgamma_w
                     , self.badds
                     , self.berases
                     ]

    self.names =   [   "Wxh"
                     , "Wrh"
                     , "Who"
                     , "Woy"
                     , "Wok_r"
                     , "Wok_w"
                     , "Wobeta_r"
                     , "Wobeta_w"
                     , "Wog_r"
                     , "Wog_w"
                     , "Wos_r"
                     , "Wos_w"
                     , "Wogamma_r"
                     , "Wogamma_w"
                     , "Woadds"
                     , "Woerases"
                     , "bh"
                     , "by"
                     , "bo"
                     , "bk_r"
                     , "bk_w"
                     , "bbeta_r"
                     , "bbeta_w"
                     , "bg_r"
                     , "bg_w"
                     , "bs_r"
                     , "bs_w"
                     , "bgamma_r"
                     , "bgamma_w"
                     , "badds"
                     , "berases"
                     ]

  def lossFun(self, inputs, targets, verbose):
    """
    inputs,targets are both list of integers.
    where in this case, H is hidden_size from above
    returns the loss, gradients on model parameters, and last hidden state
    n is the counter we're on, just for debugging
    """

    # could have fprop not do anything about the ps
    # having to get the ps out is messing us up

    def fprop(params):

      [Wxh, Wrh, Who, Woy, Wok_r, Wok_w, Wobeta_r, Wobeta_w
      , Wog_r, Wog_w, Wos_r, Wos_w, Wogamma_r, Wogamma_w, Woadds, Woerases
      , bh, by, bo, bk_r, bk_w, bbeta_r, bbeta_w
      , bg_r, bg_w, bs_r, bs_w, bgamma_r, bgamma_w, badds, berases] = params

      xs, hs, ys, ps, ts, rs, os = {}, {}, {}, {}, {}, {}, {}
      k_rs, beta_rs, g_rs, s_rs, gamma_rs = {},{},{},{},{}
      k_ws, beta_ws, g_ws, s_ws, gamma_ws = {},{},{},{},{}
      adds, erases = {},{}
      w_ws, w_rs = {},{} # read weights and write weights
      mems = {} # the state of the memory at every timestep
      # rs stores the value read out of memory
      rs[-1] = self.rsInit 
      #print "first rs"
      #print rs[-1].shape
      # TODO: if we are not allowing neg values in otherwise
      # then how much sense does it make to init mem to some negs
      mems[-1] = self.memsInit 
      w_ws_init = self.w_ws_initInit
      w_rs_init = self.w_rs_initInit
      w_ws[-1] = softmax(w_ws_init)
      w_rs[-1] = softmax(w_rs_init)
      loss = 0

      if False:
        print "w_ws[-1]"
        print w_ws[-1]
        print "w_rs[-1]"
        print w_rs[-1]

      for t in xrange(len(inputs)):

        if False:
          print "t:", t

        xs[t] = np.reshape(np.array(inputs[t]),inputs[t].shape[::-1])

        #TODO: could this just be a ReLu?
        hs[t] = np.tanh(np.dot(Wxh, xs[t]) + np.dot(Wrh, np.reshape(rs[t-1],(self.M,1))) + bh)
        # TODO: seems like we could turn this into RNN controller
        # simply by mapping o back around using affine into h[t+1]
        # along with x[t+1] and r_t

        # o is analogous to o' in the LTT paper
        # TODO: in CGT, he doesn't activate what is his equivalent of the o layer
        # but I only have one in mine
        os[t] = np.tanh(np.dot(Who, hs[t]) + bo)

        # parameters to the read head
        # TODO: play with rectification of beta and gamma
        # TODO: what are allowed values in memory?
        # that will affect what values k should take
        k_rs[t] = np.tanh(np.dot(Wok_r,os[t]) + bk_r)
        beta_rs[t] = softplus(np.dot(Wobeta_r,os[t]) + bbeta_r)
        g_rs[t] = sigmoid(np.dot(Wog_r,os[t]) + bg_r)
        s_rs[t] = softmax(np.dot(Wos_r,os[t]) + bs_r)
        gamma_rs[t] = 1 + sigmoid(np.dot(Wogamma_r, os[t]) + bgamma_r)

        # parameters to the write head
        k_ws[t] = np.tanh(np.dot(Wok_w,os[t]) + bk_w)
        beta_ws[t] = softplus(np.dot(Wobeta_w,os[t]) + bbeta_w)
        g_ws[t] = sigmoid(np.dot(Wog_w,os[t]) + bg_w)
        s_ws[t] = softmax(np.dot(Wos_w,os[t]) + bs_w)
        gamma_ws[t] = 1 + sigmoid(np.dot(Wogamma_w, os[t]) + bgamma_w)

        # the erase and add vectors
        # these are also parameters to the write head
        # but they describe "what" is to be written rather than "where"
        adds[t] = np.tanh(np.dot(Woadds, os[t]) + badds)
        erases[t] = sigmoid(np.dot(Woerases, os[t]) + berases) 

        w_ws[t] = addressing.create_weights(   k_ws[t]
                                             , beta_ws[t]
                                             , g_ws[t]
                                             , s_ws[t]
                                             , gamma_ws[t]
                                             , w_ws[t-1]
                                             , mems[t-1])

        if False:
          print "computing the write weights"
          print "k_ws[t]"
          print k_ws[t]

          print "beta_ws[t]"
          print beta_ws[t]

          print "g_ws[t]"
          print g_ws[t]

          print "s_ws[t]"
          print s_ws[t]

          print "gamma_ws[t]"
          print gamma_ws[t]

          print "w_ws[t-1]"
          print w_ws[t-1]

          print "mems[t-1]"
          print mems[t-1]

          print "w_ws[t]"
          print w_ws[t]
          #sys.exit(1)
          pass

        w_rs[t] = addressing.create_weights(   k_rs[t]
                                             , beta_rs[t]
                                             , g_rs[t]
                                             , s_rs[t]
                                             , gamma_rs[t]
                                             , w_rs[t-1]
                                             , mems[t-1])

        if False:
          print "computing the read weights"
          print "k_rs[t]"
          print k_rs[t]

          print "beta_rs[t]"
          print beta_rs[t]

          print "g_rs[t]"
          print g_rs[t]

          print "s_rs[t]"
          print s_rs[t]

          print "gamma_rs[t]"
          print gamma_rs[t]

          print "w_rs[t-1]"
          print w_rs[t-1]

          print "mems[t-1]"
          print mems[t-1]

          print "w_rs[t]"
          print w_rs[t]

        if False:
            print "w_rs[t]"
            print w_rs[t]
            print "w_ws[t]"
            print w_ws[t]

        ys[t] = np.dot(Woy, os[t]) + by
        ps[t] = sigmoid(ys[t])

        one = np.ones(ps[t].shape)
        ts[t] = np.reshape(np.array(targets[t]),(self.out_size,1))
        if False:
          print "ps[t]" 
          print ps[t]
          print "ts[t]"
          print ts[t]
        epsilon = 2**-23 # to prevent log(0)
        a = np.multiply(ts[t] , np.log(ps[t] + epsilon))
        b = np.multiply(one - ts[t], np.log(one-ps[t] + epsilon))
        loss = loss - (a + b)
        if False:
          print "loss"
          print loss

        # read from the memory
        # TODO: are we reading from last memory or this one?
          # sort of seems like no point reading from this one
          # if you're going to write something just to read it out this 
          # time, why not just write that straight to output10
        if False:
          tol = 0.02
          if np.abs(np.sum(w_rs[t]) - 1) > tol:
            print "read sum is wrong"
            print w_rs[t]
            print np.abs(np.sum(w_rs[t]) - 1)
            sys.exit(1)
          if np.abs(np.sum(w_ws[t]) - 1) > tol:
            print "write sum is wrong"
            print w_ws[t]
            print np.abs(np.sum(w_ws[t]) - 1)
            sys.exit(1)

        rs[t] = memory.read(mems[t-1],w_rs[t])

        # write into the memory
        mems[t] = memory.write(mems[t-1],w_ws[t],erases[t],adds[t])

      return loss, ps, w_rs, w_ws, adds, erases

    def training_loss(params):

      # wrap so that autograd works
      loss, ps, reads, writes, adds, erases = fprop(params)
      return np.sum(loss) 

    def bprop(params):
      f = grad(training_loss)
      return f(params)

    loss, ps, reads, writes, adds, erases = fprop(self.weights)
    deltas = bprop(self.weights)
    if False:
      print "PARAMETERS AND DELTAS"
      for n,d,p in zip(self.names, deltas, self.weights):
        print "NAME:"
        print n
        print "PARAMS:"
        print p 
        print "DELTAS:"
        print d
        pass

    return loss, deltas, ps, reads, writes, adds, erases
