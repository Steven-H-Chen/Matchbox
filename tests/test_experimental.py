from matchbox.experimental import check_points, check_instant_win

def test_three_in_a_row_scores():
    # 5×5 board with one horizontal “X X X” at row 0
    b = ["X","X","X"," "," ",
         " "," "," "," "," ",
         " "," "," "," "," ",
         " "," "," "," "," ",
         " "," "," "," "," "]
    assert check_points(b, "X") == 1

def test_instant_five_in_a_row():
    # diagonal 5-in-a-row
    b = ["X"," "," "," "," ",
         " ","X"," "," "," ",
         " "," ","X"," "," ",
         " "," "," ","X"," ",
         " "," "," "," ","X"]
    assert check_instant_win(b, "X")
