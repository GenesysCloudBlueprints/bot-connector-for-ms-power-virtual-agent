#!/bin/bash

count_failed_case=$(jq '.failed|length' linter-result.json)
# count_success_case=$(jq '.success|length' linter-result.json)

# Display failed cases first
counter=0
while [ $counter -lt $count_failed_case ]
do
    failed_case=$(jq .failed[$counter].description linter-result.json)
    id=$(jq ".failed[$counter].id" -r linter-result.json)

    line_counter=0
    count_line_highlights=$(jq ".failed[$counter].fileHighlights|length" linter-result.json)
    while [ $line_counter -lt $count_line_highlights ]
    do
        path=$(jq ".failed[$counter].fileHighlights[$line_counter].path" -r linter-result.json)
        lineFrom=$(jq ".failed[$counter].fileHighlights[$line_counter].lineNumber" linter-result.json)
        lineCount=$(jq ".failed[$counter].fileHighlights[$line_counter].lineCount" linter-result.json)
        lineCount=$(($lineCount-1))
        lineTo=$(($lineFrom+$lineCount))
        lineContent=$(jq ".failed[$counter].fileHighlights[$line_counter].lineContent" linter-result.json)
        
        echo "::error file=$path,line=$lineFrom,endLine=$lineTo,title=$id::$failed_case"
        if [ $lineCount -eq 0 ]
        then
            echo "(ln. $lineFrom) - $lineContent"
        else
            echo "(ln. $lineFrom - $lineTo) - $lineContent"
        fi

        ((line_counter++))
    done

    # If no line highlights show the case anyway
    if [ $count_line_highlights -eq 0 ]
    then
        echo "::error title=$id::$failed_case"
    fi

    ((counter++))
done

# # Display success cases
# counter=0
# while [ $counter -lt $count_success_case ]
# do
#     success_case=$(jq .success[$counter].description linter-result.json)
#     id=$(jq ".success[$counter].id" -r linter-result.json)

#     line_counter=0
#     count_line_highlights=$(jq ".success[$counter].fileHighlights|length" linter-result.json)
#     while [ $line_counter -lt $count_line_highlights ]
#     do
#         path=$(jq ".success[$counter].fileHighlights[$line_counter].path" -r linter-result.json)
#         lineFrom=$(jq ".success[$counter].fileHighlights[$line_counter].lineNumber" linter-result.json)
#         lineCount=$(jq ".success[$counter].fileHighlights[$line_counter].lineCount" linter-result.json)
#         lineCount=$(($lineCount-1))
#         lineTo=$(($lineFrom+$lineCount))
#         lineContent=$(jq ".success[$counter].fileHighlights[$line_counter].lineContent" linter-result.json)
        
#         echo "::notice file=$path,line=$lineFrom,endLine=$lineTo,title=$id::$success_case"
#         if [ $lineCount -eq 0 ]
#         then
#             echo "(ln. $lineFrom) - $lineContent"
#         else
#             echo "(ln. $lineFrom - $lineTo) - $lineContent"
#         fi
        
#         ((line_counter++))
#     done

#     # If no line highlights show the case anyway
#     if [ $count_line_highlights -eq 0 ]
#     then
#         echo "::notice title=$id::$success_case"
#     fi

#     ((counter++))
# done

if [ $count_failed_case -gt 0 ]
then
    exit 1
fi
