#!/usr/bin/python

"""
Unit tests for last.py.
"""

import last
import unittest

class TestFunctions(unittest.TestCase):
    def testjoin(self):
        """Test join."""
        self.assertEqual(last.join([['f1', 'f2'], ['f3']]),
                         ['f1', 'f2', 'f3'])

    def testrange(self):
        """Test subrange."""
        self.assertEqual(last.subrange([]),              (0, 0)) # []
        self.assertEqual(last.subrange([1]),             (0, 1)) # [1]
        self.assertEqual(last.subrange([1, 1, 1, 1]),    (0, 1)) # [1]
        self.assertEqual(last.subrange([1, 1, 0, 0, 0]), (1, 3)) # [1, 0]
        self.assertEqual(last.subrange([4, 3, 2, 0, 0]), (3, 4)) # [0]
        self.assertEqual(last.subrange([4, 3, 2, 1, 0]), (0, 5)) # [4, 3, 2, 1, 0]
        self.assertEqual(last.subrange([0, 0, 0, 0, 0]), (0, 1)) # [0]
        self.assertEqual(last.subrange([1, 0, 0, 0, 0]), (0, 2)) # [1, 0]
        self.assertEqual(last.subrange([2, 1, 0, 0, 0]), (0, 3)) # [2, 1, 0]
        self.assertEqual(last.subrange([3, 2, 1, 0, 0]), (0, 4)) # [3, 2, 1, 0]
        self.assertEqual(last.subrange([4, 3, 2, 1, 0]), (0, 5)) # [4, 3, 2, 1, 0]
        self.assertEqual(last.subrange([5, 4, 3, 2, 1]), (0, 5)) # [5, 4, 3, 2, 1]
        self.assertEqual(last.subrange([4, 5, 0, 0, 0]), (2, 3)) # [0]
        self.assertEqual(last.subrange([4, 5, 1, 0, 0]), (2, 4)) # [1, 0]
        self.assertEqual(last.subrange([4, 5, 2, 1, 0]), (2, 5)) # [2, 1, 0]
        self.assertEqual(last.subrange([4, 5, 3, 2, 1]), (2, 5)) # [3, 2, 1]
        self.assertEqual(last.subrange([4, 5, 4, 3, 2]), (1, 5)) # [5, 4, 3, 2]
        self.assertEqual(last.subrange([1, 2, 3, 4, 5]), (0, 1)) # [1]
        self.assertEqual(last.subrange([2, 2, 3, 4, 5]), (0, 1)) # [2]
        self.assertEqual(last.subrange([3, 2, 3, 4, 5]), (0, 2)) # [3, 2]

    def testmerge(self):
        """Test performmerge."""
        self.assertEqual(last.performmerge([], 0, 0, False),
                         [])
        self.assertEqual(last.performmerge([['a', 'b', 'c']],
                                           0, 0, False),
                         ['a', 'b', 'c'])
        self.assertEqual(last.performmerge([['a1', 'a2', 'a3', 'a4'],
                                            ['b1', 'b2', 'b3', 'b4'],
                                            ['c1', 'c2', 'c3', 'c4'],
                                            ['d1', 'd2', 'd3', 'd4']],
                                           0, 0, False, False),
                         ['a1', 'b1', 'c1', 'd1',
                          'a2', 'b2', 'c2', 'd2',
                          'a3', 'b3', 'c3', 'd3',
                          'a4', 'b4', 'c4', 'd4'])
        self.assertEqual(last.performmerge([['a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7'],
                                            ['b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7'],
                                            ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7'],
                                            ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7'],
                                            ['e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7'],
                                            ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7']],
                                           5, 5, False, False),
                         ['a1', 'b1', 'c1', 'd1', 'e1',
                          'a2', 'b2', 'c2', 'd2', 'e2',
                          'a3', 'b3', 'c3', 'd3', 'e3',
                          'a4', 'b4', 'c4', 'd4', 'e4',
                          'a5', 'b5', 'c5', 'd5', 'e5',
                          'f1', 'a6', 'b6', 'c6', 'd6',
                          'f2', 'a7', 'b7', 'c7', 'd7',
                          'f3', 'e6', 'f4', 'e7', 'f5',
                          'f6', 'f7'])
        self.assertEqual(last.performmerge([['a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9'],
                                            ['b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'b9'],
                                            ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9'],
                                            ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8', 'd9'],
                                            ['e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8', 'e9'],
                                            ['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9'],
                                            ['g1', 'g2', 'g3', 'g4', 'g5', 'g6', 'g7', 'g8', 'g9'],
                                            ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9'],
                                            ['i1', 'i2', 'i3', 'i4', 'i5', 'i6', 'i7', 'i8', 'i9'],
                                            ['j1', 'j2', 'j3', 'j4', 'j5', 'j6', 'j7', 'j8', 'j9'],
                                            ['k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8', 'k9'],
                                            ['l1', 'l2', 'l3', 'l4', 'l5', 'l6', 'l7', 'l8', 'l9']],
                                           5, 5, False, True),
                         ['a1', 'a2', 'b1', 'a3', 'b2', 'c1', 'a4', 'b3', 'c2',
                          'd1', 'a5', 'b4', 'c3', 'd2', 'e1', 'b5', 'c4', 'd3',
                          'e2', 'f1', 'c5', 'd4', 'e3', 'f2', 'g1', 'd5', 'e4',
                          'f3', 'g2', 'h1', 'e5', 'f4', 'g3', 'h2', 'i1', 'f5',
                          'g4', 'h3', 'i2', 'j1', 'g5', 'h4', 'i3', 'j2', 'k1',
                          'h5', 'i4', 'j3', 'k2', 'l1', 'i5', 'j4', 'k3', 'l2',
                          'a6', 'j5', 'k4', 'l3', 'a7', 'b6', 'k5', 'l4', 'a8',
                          'b7', 'c6', 'l5', 'a9', 'b8', 'c7', 'd6', 'b9', 'c8',
                          'd7', 'e6', 'c9', 'd8', 'e7', 'f6', 'd9', 'e8', 'f7',
                          'g6', 'e9', 'f8', 'g7', 'h6', 'f9', 'g8', 'h7', 'i6',
                          'g9', 'h8', 'i7', 'j6', 'h9', 'i8', 'j7', 'k6', 'i9',
                          'j8', 'k7', 'l6', 'j9', 'k8', 'l7', 'k9', 'l8', 'l9'])

if __name__ == '__main__':
    unittest.main()
