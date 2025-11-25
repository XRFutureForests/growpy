#!/bin/bash

BEECH="data/output/forest/european_beech/european_beech_tree_0000.json"

echo "========================================================================"
echo "VALIDATION: Required Fields in Beech JSON"
echo "========================================================================"
echo ""

check_path() {
    local path=$1
    local file=$2
    
    # Simple check - look for the key in the JSON
    local key=$(echo "$path" | sed 's/\./\./g')
    
    if grep -q "\"${path##*.}\"" "$file" 2>/dev/null; then
        echo "✓ PASS | $path"
        return 0
    else
        echo "✗ FAIL | $path"
        return 1
    fi
}

# Check each required field
PASS=0
FAIL=0

for field in "pscale" "positions" "lengthFromRoot" "LOD_totalPscaleGradient" "budDirection" "points" "instancer_name" "instancer_pivot" "instancer_UP" "instancer_scale" "instancer_LFR" "parents" "children" "branchNumber" "phyllotaxyLeaf"; do
    if grep -q "\"$field\"" "$BEECH" 2>/dev/null; then
        echo "✓ PASS | $field"
        ((PASS++))
    else
        echo "✗ FAIL | $field"
        ((FAIL++))
    fi
done

echo ""
echo "========================================================================"
echo "Results: $PASS passed, $FAIL failed"
echo "========================================================================"

# Now check specifically for the key format issues
echo ""
echo "Key Format Check (primitives attributes should use 'values' not 'value'):"
echo ""

for attr in "instancer_name" "instancer_pivot" "instancer_UP" "instancer_N" "instancer_scale" "instancer_LFR"; do
    # Check if this attribute exists and what key it uses
    value_key=$(grep -A 3 "\"$attr\"" "$BEECH" | grep -o '"values"\|"value"' | head -1)
    if [ -n "$value_key" ]; then
        if [ "$value_key" = '"values"' ]; then
            echo "✓ $attr uses 'values' (correct)"
        else
            echo "✗ $attr uses 'value' (WRONG - should be 'values')"
        fi
    else
        echo "? $attr not found"
    fi
done
