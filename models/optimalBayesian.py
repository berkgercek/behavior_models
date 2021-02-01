from models import model
import torch, utils
import numpy as np
from torch.distributions.normal import Normal

unsqueeze = lambda x : torch.unsqueeze(torch.unsqueeze(x, 0), -1)

class optimal_Bayesian(model.Model):
    '''
        Model where the prior is based on an exponential estimation of the previous stimulus side
    '''

    def __init__(self, path_to_results, session_uuids, mouse_name, actions, stimuli, stim_side):
        name = 'optimal_bayesian'
        nb_params, lb_params, ub_params = 4, np.array([0, 0, 0, 0]), np.array([1, 1, .5, .5])
        initial_point = np.array([0.5, 0.5, 0.1, 0.1])
        std_RW = np.array([0.04, 0.04, 0.01, 0.01])
        super().__init__(name, path_to_results, session_uuids, mouse_name, actions, stimuli, stim_side, nb_params, lb_params, ub_params, std_RW, initial_point)
        self.nb_blocklengths, self.nb_typeblocks = 100, 3
        if torch.cuda.is_available():
            self.use_gpu = True
            self.device = torch.device("cuda:0")
            print("Running on the GPU")
        else:
            self.use_gpu = False
            self.device = torch.device("cpu")
            print("Running on the CPU")

    def compute_lkd(self, arr_params, act, stim, side, return_details):
        nb_chains = len(arr_params)
        zeta_pos, zeta_neg, lapse_pos, lapse_neg = torch.tensor(arr_params, device=self.device, dtype=torch.float32).T
        act, stim, side = torch.tensor(act, device=self.device, dtype=torch.float32), torch.tensor(stim, device=self.device, dtype=torch.float32), torch.tensor(side, device=self.device, dtype=torch.float32)
        nb_sessions = len(act)
        lb, tau, ub, gamma = 20, 60, 100, 0.8

        alpha = torch.zeros([nb_sessions, nb_chains, self.nb_trials, self.nb_blocklengths, self.nb_typeblocks], device=self.device, dtype=torch.float32)
        alpha[:, :, 0, 0, 1] = 1
        alpha = alpha.reshape(nb_sessions, nb_chains, -1, self.nb_typeblocks * self.nb_blocklengths)
        h = torch.zeros([nb_sessions, nb_chains, self.nb_typeblocks * self.nb_blocklengths], device=self.device, dtype=torch.float32)

        zetas = unsqueeze(zeta_pos) * (torch.unsqueeze(side,1) > 0) + unsqueeze(zeta_neg) * (torch.unsqueeze(side,1) <= 0)
        lapses = unsqueeze(lapse_pos) * (torch.unsqueeze(side,1) > 0) + unsqueeze(lapse_neg) * (torch.unsqueeze(side,1) <= 0)

        # build transition matrix
        b = torch.zeros([self.nb_blocklengths, 3, 3], device=self.device, dtype=torch.float32)
        b[1:][:,0,0], b[1:][:,1,1], b[1:][:,2,2] = 1, 1, 1 # case when l_t > 0
        b[0][0][-1], b[0][-1][0], b[0][1][np.array([0, 2])] = 1, 1, 1./2 # case when l_t = 1
        n = torch.arange(1, self.nb_blocklengths+1, device=self.device, dtype=torch.float32)
        ref    = torch.exp(-n/tau) * (lb <= n) * (ub >= n)
        hazard = torch.cummax(ref/torch.flip(torch.cumsum(torch.flip(ref, (0,)), 0) + 1e-18, (0,)), 0)[0]
        padding = torch.zeros(self.nb_blocklengths-1, device=self.device, dtype=torch.float32)
        l = torch.cat((torch.unsqueeze(hazard, -1), torch.cat(
                    (torch.diag(1 - hazard[:-1]), padding[np.newaxis]), axis=0)), axis=-1) # l_{t-1}, l_t
        transition = 1e-12 + torch.transpose(l[:,:,np.newaxis,np.newaxis] * b[np.newaxis], 1, 2).reshape(self.nb_typeblocks * self.nb_blocklengths, -1)
        ones = torch.ones(nb_sessions, device=self.device, dtype=torch.float32)

        # likelihood
        Rhos = Normal(loc=torch.unsqueeze(stim, 1), scale=zetas).cdf(0)

        for i_trial in range(self.nb_trials):
            s = side[:, i_trial]
            lks = torch.stack([gamma*(s==-1) + (1-gamma) * (s==1), ones * 1./2, gamma*(s==1) + (1-gamma)*(s==-1)]).T

            # save priors
            if i_trial > 0:
                alpha[act[:, i_trial-1]!=0, :, i_trial] = torch.sum(torch.unsqueeze(h, -1) * transition, axis=2)[act[:, i_trial-1]!=0]
                alpha[act[:, i_trial-1]==0, :, i_trial] = alpha[act[:, i_trial-1]==0, :, (i_trial-1)]
            h = alpha[:, :, i_trial] * torch.unsqueeze(lks, 1).repeat(1, 1, self.nb_blocklengths)
            h = h/torch.unsqueeze(torch.sum(h, axis=-1), -1)

        predictive = torch.sum(alpha.reshape(nb_sessions, nb_chains, -1, self.nb_blocklengths, self.nb_typeblocks), 3)
        Pis  = predictive[:, :, :, 0] * gamma + predictive[:, :, :, 1] * 0.5 + predictive[:, :, :, 2] * (1 - gamma)
        pRight, pLeft = Pis * Rhos, (1 - Pis) * (1 - Rhos)
        pActions = torch.stack((pRight/(pRight + pLeft), pLeft/(pRight + pLeft)))
        pActions = pActions * (1 - lapses) + lapses / 2.
        pActions[torch.isnan(pActions)] = 0

        p_ch     = pActions[0] * (torch.unsqueeze(act, 1) == -1) + pActions[1] * (torch.unsqueeze(act, 1) == 1) + 1 * (torch.unsqueeze(act, 1) == 0) # discard trials where agent did not answer

        p_ch_cpu = torch.tensor(p_ch.detach(), device='cpu')
        priors   = torch.tensor(Pis.detach(), device='cpu')
        logp_ch = torch.log(torch.minimum(torch.maximum(p_ch_cpu, torch.tensor(1e-8)), torch.tensor(1 - 1e-8)))

        # clean up gpu memory
        if self.use_gpu:
            del gamma, zeta_pos, zeta_neg, lapse_pos, lapse_neg, lb, tau, ub, act, stim, side, s, lks
            del alpha, h, zetas, lapses, b, n, ref, hazard, padding, l, transition, ones, Rhos
            del predictive, Pis, pRight, pLeft, pActions, p_ch
            torch.cuda.empty_cache()
            # print(torch.cuda.memory_allocated())
            # torch.cuda.empty_cache()
            # print(torch.cuda.memory_reserved())

        if return_details:
            return np.array(torch.sum(logp_ch, axis=(0, -1))), priors
        return np.array(torch.sum(logp_ch, axis=(0, -1)))

        