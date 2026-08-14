"""
test module docstring

"""
import ast
from os.path import split

def s(a,b):
    """test function docstring"""
    #
    return a+b

def m(a,b):
    """
    test multiline 
    with "edgecase"
    docstring
    """
    #test comment
    return a-b

def ml(a,b):
    '''
    test multiline 
    with 'edgecase'
    docstring single quote
    '''
    return a*b #should not be returned

def dv(a,b):
    '''test single quote'''
    return a/b

def nest0(a):
    '''test single quote'''
    def nest1(b):
        return b+1
    return nest1(a)+1