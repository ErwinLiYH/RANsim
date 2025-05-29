import random

random_seed = 42

def reset_random_seed(seed=None):
    """select a new random seed for reproducibility"""
    global random_seed
    if seed is None:
        random_seed = random.randint(0, 2**32 - 1)
    else:
        random_seed = seed

def get_random_seed():
    """get the current random seed"""
    return random_seed