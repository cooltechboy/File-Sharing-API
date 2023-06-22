from flask import *
import json
import pytest
import sqlite3


@pytest.fixture
def signup_input():
    Username = "Ankurr"
    conn = sqlite3.connect("database.db")
    Existing_Usernames = json.dumps(conn.execute("SELECT Username FROM User_Details").fetchall())
    
    return [Username, Existing_Usernames]

def test_signup(signup_input):
    check_user = signup_input[0] in json.dumps(signup_input[1])
    assert  check_user == False
    
