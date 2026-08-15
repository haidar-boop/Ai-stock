"""Out-of-sample check on symbols never used to design the rules."""
import sys
import randomization_test as rt
rt.SYMS = ["JPM","JNJ","PG","WMT","KO","DIS","BA","CAT","GE","PFE","VZ","MRK","HD","MCD"]
rt.main(int(sys.argv[1]) if len(sys.argv)>1 else 300)

