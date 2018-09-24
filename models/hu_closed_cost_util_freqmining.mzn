% Use the MiningZinc library (cover and cover_inv functions).
include "miningzinc.mzn";

% Data
array [int] of set of int: TDB :: vartype("T","I");
int: MinFreq;  % Frequency threshold
array [int] of int: costs;
array [int] of int: utils;
int: Cost;
int: Util;

% Itemset definition
var set of array_union(TDB): Items :: vartype("I");

% Constraints
constraint card(cover(Items, TDB)) >= MinFreq;
constraint Items = cover_inv(cover(Items,TDB),TDB);
constraint sum(i in ub(Items)) (bool2int(i in Items)*costs[i]) <= Cost;
constraint sum(i in ub(Items)) (bool2int(i in Items)*utils[i]) >= Util;

% Search
solve
    :: item_search(Items)
    satisfy;

output [show(Items)];
