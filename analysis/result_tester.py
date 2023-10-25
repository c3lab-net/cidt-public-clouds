def parse_list_from_line(line):
    try:
        # Using eval to parse the list from string. 
        # Note: eval can be unsafe if you're running it on untrusted input.
        data = eval(line)
        if isinstance(data, list):
            return data
        else:
            print("The content of the line is not a list.")
            return None
    except:
        print("Could not parse a list from the line.")
        return None

def compare_list_lengths(file1_path, file2_path):
    falseCounter = 0
    trueCounter = 0
    line_number = 0 
    with open(file1_path, 'r') as file1, open(file2_path, 'r') as file2:              
        while True:
            line1 = file1.readline()
            line2 = file2.readline()
            
            # Break the loop if both files have reached their end
            if not line1 and not line2:
                break
            
            # Parse lists from lines
            list1 = parse_list_from_line(line1) if line1 else None
            list2 = parse_list_from_line(line2) if line2 else None
            
            # Check if both lists have the same length
            if list1 is not None and list2 is not None:
                if len(list1) == len(list2):
                    trueCounter += 1
                else:
                    falseCounter += 1
            elif list1 is not None or list2 is not None:
                print(f"Line {line_number}: Only one list is present.")
                falseCounter += 1
            
            line_number += 1
    print(f"Test finished, for {line_number} result, {trueCounter} are in the same length, {falseCounter} are not.")
def list_length_statistics(file_path):
    # Initialize a dictionary to store the count of lists in each length category
    length_categories = {'5 or more': 0, '4': 0, '3': 0, '2': 0}
    
    with open(file_path, 'r') as file:
        for line in file:
            # Using eval to parse the list from string.
            # Note: eval can be unsafe if you're running it on untrusted input.
            try:
                data = eval(line)
                if isinstance(data, list):
                    list_length = len(data)
                    if list_length >= 5:
                        length_categories['5 or more'] += 1
                    elif list_length == 4:
                        length_categories['4'] += 1
                    elif list_length == 3:
                        length_categories['3'] += 1
                    elif list_length == 2:
                        length_categories['2'] += 1
                else:
                    print("The content of the line is not a list.")
            except:
                print("Could not parse a list from the line.")
    
    # Print the length distribution statistics
    print("Length Distribution Statistics:")
    for category, count in length_categories.items():
        print(f"Lists of length {category}: {count}")
# Specify your file paths here
file1_path = './answer.by_ip'
file2_path = './routes.aws.us-west-1.us-east-1.by_ip'

compare_list_lengths(file1_path, file2_path)
list_length_statistics(file1_path)