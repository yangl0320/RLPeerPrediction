# RLModule is responsible to decide the action
import abc
import numpy as np


# The base class of RL
class RLBase(object):
    __metaclass__ = abc.ABCMeta

    # The discount factor
    gamma = 0.9

    # The action set (prices goes from the smallest to the largest)
    ActionSet = [0.1, 1, 5, 10]

    @abc.abstractmethod
    def decide(self, start = False):
        """Decide the action a_t"""
        return

    @abc.abstractmethod
    def observe(self, a, r, s, start = False, terminal = False):
        """Observe <reward_t, state_t+1> """
        return


# Gaussian Process SARSA
class GpSarsa(RLBase):

    def __init__(self, len_state: int):
        # The noisy level of the Gaussian process
        self.sigma = 0.02
        # Observation history
        self.Hist = []  # <State, Action>
        self.len_state = len_state
        self.rHist = []  # Reward
        # The covariance matrix
        self.Cov = []
        # Current State
        self.S = []
        # H matrix
        self.invH = []
        # Gaussian Process Parameters
        self.Alpha = None
        self.C = None

    def decide(self):
        """We use Thompson sampling to decide the next-step action."""
        if len(self.Hist) == 0:
            '''At the first step, choose the lowest price'''
            return RLBase.ActionSet[0]
        else:
            '''Firstly, update the Gaussian process model'''
            self.gpRegression()
            '''Secondly, compute the prediction of the Gaussian process'''
            q = []
            z = self.S.copy()
            z.append(self.ActionSet[0])
            for a in RLBase.ActionSet:
                z[-1] = a
                q.append(self.gpPredict(z))
            '''Thirdly, select the action with the largest Q value'''
            pos = q.index(max(q))
            return RLBase.ActionSet[pos]

    def observe(self, a, r, s, start = False, terminal = False):
        """Observe the environment change after action a"""
        '''Add the data to the observation history'''
        if len(self.S)>0:
            self.Hist.append(list(self.S)+[a])
            self.rHist.append(r)
        '''Update the current state'''
        self.S = list(s.copy())

    # noinspection PyUnresolvedReferences
    def kernel(self, z1: np.array, z2: np.array) -> float:
        x1 = np.mean(z1[0: self.len_state: 2])
        x2 = np.mean(z1[1: self.len_state: 2])
        x3 = np.mean(z2[0: self.len_state: 2])
        x4 = np.mean(z2[1: self.len_state: 2])
        dist_w = np.exp(-1.0*((x1 - x3)**2 + (x2 - x4)**2)) # Here, 4 = 2^2
        x5 = z1[self.len_state] - z2[self.len_state]
        dist_A = np.exp(-1.0*(x5**2)) # Here, 0.25 = 0.5^2
        return dist_A*dist_w
        # diff = (z1 - z2)**2
        # '''The difference between different workers'''
        # distW = np.exp(-4*(diff[0:-1:2]+diff[1:-1:2]))
        # '''The difference between actions'''
        # distA = np.exp(-0.01*diff[-1])
        # noinspection PyTypeChecker
        # return np.sum(distW)*distA
        #return np.exp(-0.5*np.sum(np.abs(diff)))

    def gpRegression(self):
        """Compute the Gaussian Process model"""
        ''''Compute the covariance between new observation and old ones'''
        k_cov = [self.kernel(np.asarray(self.Hist[-1]), np.asarray(z)) for z in self.Hist]
        '''Add these data to the covariance table'''
        for (c1, c2) in zip(self.Cov, k_cov):
            c1.append(c2)
        self.Cov.append(k_cov)
        '''Compute the inverse of the covariance'''
        T = len(self.Cov)
        matCov = np.asarray(self.Cov)
        invCov = np.linalg.inv(matCov+self.sigma*self.sigma*np.identity(T))
        '''Update the inverse H matrix'''
        for i in range(T-1):
            self.invH[i].append(RLBase.gamma**(T-i-1))
        self.invH.append([0]*(T-1)+[1])
        matInvH = np.asarray(self.invH)
        '''Compute alpha and C matrix'''
        self.Alpha = np.dot(np.dot(invCov, matInvH), self.rHist)
        self.C = invCov
        return

    def gpPredict(self, z):
        """Use the Gaussian Process model to predict Q(z=<s,a>)"""
        '''Compute the mean value and variance'''
        k_cov = [self.kernel(np.asarray(z), np.asarray(el)) for el in self.Hist]
        vec_k_cov = np.asarray(k_cov)
        k0 = self.kernel(np.asarray(z), np.asarray(z))
        meanVal = vec_k_cov.dot(self.Alpha)
        varVal = k0 - vec_k_cov.dot(np.dot(self.C,vec_k_cov))
        '''Generate a sample from the prediction'''
        return np.random.normal(meanVal, np.sqrt(varVal))


# Gaussian Process SARSA
class EpGpSarsa(RLBase):
    def __init__(self):
        # The noisy level of the Gaussian process
        self.sigma = 0.2
        self.kernel_sigma = np.array([10,0.1,0.05,0.05])
        self.explore_prob = 0.2
        # Observation history
        self.Hist = []  # <State, Action, Action>
        self.R = []  # Reward
        # The covariance matrix
        self.Cov = []
        # Current State
        self.z = None
        # H matrix
        self.H = []
        # Gaussian Process Parameters
        self.A = None
        self.C = None
        # Add r flag
        r_flag = False


    def kernel(self, z1: np.array, z2: np.array) -> float:
        d = self.kernel_sigma * (z1-z2)
        dd = np.sum(d**2)
        return np.exp(-1.0*dd)

    def observe(self, a, r, s, start = False, terminal = False):
        # Add to the history
        if start is False:
            self.Hist.append(list(self.z) + [a])
            self.R.append(r)

        # Update Current State
        if terminal is False:
            self.z = list(s.copy()) + [a]
        else:
            self.z.clear()
        # Update the H mat
        if start is True:
            for row in self.H:
                row.append(0)
        else:
            self.H.append([0]*len(self.H)+[1])
            self.gpRegression()
            if terminal is False:
                for row in self.H[0:-1]:
                    row.append(0)
                self.H[-1].append(-self.gamma)

    def gpRegression(self):
        """Compute the Gaussian Process model"""
        # Compute the covariance between new observation and old ones
        k_cov = [self.kernel(np.asarray(self.Hist[-1]), np.asarray(z)) for z in self.Hist]
        # Add these data to the covariance table
        for (c1, c2) in zip(self.Cov, k_cov):
            c1.append(c2)
        self.Cov.append(k_cov)
        # Compute the inverse of the covariance
        T = len(self.H)
        K = np.asmatrix(self.Cov)
        '''Compute alpha and C matrix'''
        HH = np.asmatrix(self.H)
        Temp = HH.T * np.linalg.inv(HH * K * HH.T + HH * HH.T * self.sigma * self.sigma)
        r = np.asmatrix(self.R)
        self.A = Temp * r.T
        self.C = Temp * HH

    def decide(self, start = False):
        """We use Thompson sampling to decide the next-step action."""
        # At the first step, choose the lowest price
        th = np.random.rand()
        if th<self.explore_prob:
            return np.random.choice(RLBase.ActionSet)
        else:
            if len(self.H) == 0:
                return RLBase.ActionSet[0]
            if start is True:
                self.z = [0.5, 0.0, RLBase.ActionSet[0]]
            # Calculate the prediction
            q = np.zeros(len(RLBase.ActionSet))
            x = self.z.copy() + [0]
            for i in range(len(RLBase.ActionSet)):
                x[-1] = RLBase.ActionSet[i]
                q[i] = self.gpPredict(x)
            print("Q: ", q)
            pos = np.argmax(q)
            return RLBase.ActionSet[pos]

    def gpPredict(self, z):
        """Use the Gaussian Process model to predict Q(z=<s,a>)"""
        # Compute the mean value and variance
        k_cov = [self.kernel(np.asarray(z), np.asarray(el)) for el in self.Hist]
        vec_k_cov = np.asmatrix(k_cov)
        k0 = self.kernel(np.asarray(z), np.asarray(z))
        meanVal = vec_k_cov * self.A
        varVal = k0 - vec_k_cov * self.C * vec_k_cov.T
        # print(meanVal, '\t', varVal)
        # Generate a sample from the prediction
        # return np.random.normal(meanVal, np.sqrt(varVal))
        return meanVal