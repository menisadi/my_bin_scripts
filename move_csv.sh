#!/bin/zsh

# Get the last downloaded CSV file in ~/Downloads
last_csv=$(ls -t ~/Downloads/*.csv | head -n1)

# Display details of the CSV file
echo "Original name: $(basename "$last_csv")"
echo "Time modified: $(date -r "$last_csv")"
echo "Size: $(du -h "$last_csv" | cut -f1)"

# Prompt the user to enter a new name for the file
echo -n "Enter a new name for the file: "
read new_name

# Add .csv extension if not already included
if [[ $new_name != *.csv ]]; then
    new_name="$new_name.csv"
fi

# Move the file to ~/code/work/data with the new name
mv "$last_csv" ~/code/work/data/"$new_name"
