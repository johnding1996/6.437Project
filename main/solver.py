import numpy as np
from _hungarian import linear_sum_assignment
from util import to_text

def shuffle(plaincode, length):
    start_index = np.random.randint(plaincode.shape[0]-length)
    return plaincode[start_index:start_index+length]

def encrypt(plaincode, order):
    f_true = np.random.permutation(order)
    ciphercode = f_true[plaincode]
    return ciphercode, f_true

def initialize(lp, c, num, order):
    cost = (np.tile(np.exp(lp[0]).reshape(order,1), (1,order))-np.tile((c[0]/np.sum(c[0])).reshape(1,order), (order,1)))**2
    linear_sum_assignment(cost)
    f_pred = linear_sum_assignment(cost)[1]
    x = np.tile(f_pred.reshape(1,order), (num,1))
    return change_without_mask(x, None, None)[1]

def reshape_lp(lp, num):
    return [np.tile(np.expand_dims(lp[0], axis=0), (num,1)),
            np.tile(np.expand_dims(lp[1], axis=0), (num,1,1)),
            np.tile(np.expand_dims(lp[2], axis=0), (num,1,1,1))]

def mask(x, threshold):
    m = np.empty(x.shape[1], dtype=np.bool)
    xmj = np.zeros(x.shape[1])
    for j in range(x.shape[1]):
        count = np.bincount(x[:,j], minlength=x.shape[1])
        m[j] = (np.max(count) < x.shape[0]*threshold)
        xmj[j] = np.argmax(count)
    return m, xmj.reshape((1,x.shape[1]))

def cumulate(xmj, xmjp, xmj_cum, m, fix_interval):
    for j in range(xmj.shape[1]):
        if xmj[0,j] != xmjp[0,j]:
            xmj_cum[0,j] = 0
        else:
            xmj_cum[0,j] += 1
    return ~np.logical_and(~m, xmj_cum > fix_interval).reshape(xmj.shape[1]), xmj_cum

def change_without_mask(x, m, xmj):
    def _swap(_x):
        idx = np.random.choice(x.shape[1], 2, replace=False)
        _x[idx] = _x[idx[::-1]]
        return _x
    xp = np.apply_along_axis(_swap, 1, np.copy(x))
    return x, xp

def change_with_mask(x, m, xmj):
    def _fix(_x):
        conflict_idx = np.logical_and(~m, xmj[0,]!=_x)
        if np.any(conflict_idx):
            required_codes = list(set(xmj[0,conflict_idx]) - set(_x[conflict_idx]))
            extra_codes = list(set(_x[conflict_idx]) - set(xmj[0,conflict_idx]))
            change_mask = np.empty(xmj.shape[1], dtype=np.bool)
            for j in range(xmj.shape[1]):
                change_mask[j] =  (_x[j] in required_codes)
            _x[~m] = xmj[0,~m]
            _x[change_mask] = np.random.permutation(np.array(extra_codes))
        return _x
    def _swap(_x):
        idx = np.random.choice(x.shape[1], 2, replace=False)
        _x[idx] = _x[idx[::-1]]
        return _x
    x = np.apply_along_axis(_fix, 1, x)
    xp = np.apply_along_axis(_swap, 1, np.copy(x))
    return x, xp

def count(ciphercode, order):
    c1 = np.zeros(order)
    np.add.at(c1, ciphercode, 1)
    c2 = np.zeros((order, order))
    np.add.at(c2, (ciphercode[:-1], ciphercode[1:]), 1)
    c3 = np.zeros((order, order, order))
    np.add.at(c3, (ciphercode[:-2], ciphercode[1:-1], ciphercode[2:]), 1)
    return [c1, c2, c3]

def ngram_log_prob(x, lp, c, w):
    num = x.shape[0]
    order = x.shape[1]
    x_lp = np.sum(c[1][np.tile(x.reshape((num,order,1)), (1,1,order)), 
                        np.tile(x.reshape((num,1,order)), (1,order,1))
                       ]*lp[1], axis=(1,2))*w[0]
    x_lp += np.sum(c[2][np.tile(x.reshape((num,order,1,1)), (1,1,order,order)),
                        np.tile(x.reshape((num,1,order,1)), (1,order,1,order)),
                        np.tile(x.reshape((num,1,1,order)), (1,order,order,1))
                       ]*lp[2], axis=(1,2,3))*w[1]
    return x_lp

def word_log_prob(x, wlp, ciphercode, w):
    length = ciphercode.shape[0]
    if length < 400:
        return np.zeros(x.shape[0])
    xinv = np.argsort(x, axis=1)
    decryptedcode = xinv[:,ciphercode[:400]]
    x_lp = np.zeros(x.shape[0])
    for i in range(x.shape[0]):
        wl = decryptedcode[i,]
        wl = wl[wl!=27]
        wl = ''.join(to_text(wl))
        wl = wl.split(' ')
        if len(wl) < 40:
            x_lp[i] = 40*(-40)
            continue
        for wd in wl[:40]:
            x_lp[i] += wlp.get(wd, -40)
    return x_lp*w[2]

def best(x, x_lp):
    return x[np.argmax(x_lp),].reshape(1,x.shape[1])

def update(x, xp, p_delta):
    rs = (p_delta > 0).reshape((x.shape[0],1)).astype(np.int)
    return rs*xp+(1-rs)*x, rs

def accuracy(x, ciphercode, plaincode):
    if np.isnan(x).any():
        return np.nan
    xinv = np.argsort(x, axis=1)
    plaincode = np.repeat(plaincode.reshape((1,-1)), x.shape[0], axis=0)
    return np.mean((xinv[:,ciphercode] == plaincode).astype(np.int))

def mapping_accuracy(x, f_true):
    func_acc = np.zeros(x.shape[0])
    for i in range(x.shape[0]):
        func_acc[i] = np.mean(x[i,] == f_true)
    return np.mean(func_acc)

def error_map(x, f_true):
    xinv = np.argsort(x, axis=1)
    f_true_inv = np.argsort(f_true)
    error_map = np.zeros((x.shape[1], x.shape[1]))
    for i in range(x.shape[0]):
        error_map[f_true_inv[xinv[i,] != f_true_inv].astype(np.int), 
                  xinv[i,][xinv[i,] != f_true_inv].astype(np.int)] += 1
    return error_map

def grammar_validity(x, ciphercode):
    xinv = np.argsort(x, axis=1)
    plaincode = xinv[:,ciphercode]
    return 1-np.mean(np.any(np.logical_and(plaincode[:,:-1] == 27, plaincode[:,1:] != 26), axis=1))

def solve(testcc, lp, wlp, num, order, maxiter, verbose_interval, w, threshold, fix_interval):
    c = count(testcc, order)
    x = initialize(lp, c, num, order)
    rlp = reshape_lp(lp, num)
    rs_cum = np.zeros((num,1))
    xmj_cum = np.zeros((1,order))
    m, xmj = mask(x, threshold)
    for it in range(maxiter):
        m, xmjp = mask(x, threshold)
        m, xmj_cum = cumulate(xmj, xmjp, xmj_cum, m, fix_interval)
        xmj = xmjp
        if np.mean(m) == 0 and it > 3*fix_interval:
            break
        x, xp = change_with_mask(x, m, xmj)
        p_x = ngram_log_prob(x, rlp, c, w) + word_log_prob(x, wlp, testcc, w)
        p_xp = ngram_log_prob(xp, rlp, c, w) + word_log_prob(x, wlp, testcc, w)
        p_delta = p_xp - p_x
        x, rs = update(x, xp, p_delta)
        rs_cum += rs
        if verbose_interval > 0 and it % verbose_interval == 0:
            print("it:{}, log_p:{:1.3e}, acpt_r:{:1.3e}, p_fix:{:1.3e}".format(
                  str(it).zfill(4), np.mean(p_x), np.mean(rs_cum)/verbose_interval, 1-np.mean(m)))
            rs_cum = np.zeros((num,1))
    xmj = xmj.reshape(xmj.shape[-1])
    return np.argsort(xmj)[testcc], xmj