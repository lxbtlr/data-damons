from collections import deque
import math
def bisect_range(end, start, mode=None):
    """
    Yields integers between start and end (inclusive) 
    using a recursive bisection strategy.
    """
    if mode==True:
        # Safely handle numbers <= 0 since powers of 2 are strictly positive
        safe_start = max(1, start)
        if safe_start > end:
            print("safe > end")
            return
            
        # Find the integer bounds for our base-2 exponents
        min_exp = math.ceil(math.log2(safe_start))
        max_exp = math.floor(math.log2(end))
        
        if min_exp > max_exp:
            print("min > max")
            return
            
        # Generate the strict list of base-2 integers in range
        powers_of_2 = [2**i for i in range(min_exp, max_exp + 1)]
        
        # 1. Yield boundaries of the powers of 2
        yield powers_of_2[0]
        if len(powers_of_2) > 1:
            yield powers_of_2[-1]
            
        # 2. Bisect the indices of our powers_of_2 list
        queue = deque([(0, len(powers_of_2) - 1)])
        seen = {0, len(powers_of_2) - 1}
        
        while queue:
            low, high = queue.popleft()
            mid = (low + high) // 2
            
            if mid not in seen:
                yield powers_of_2[mid]
                seen.add(mid)
                
                queue.append((low, mid))
                queue.append((mid, high))
                
    else:
        # 1. Yield the boundaries first
        yield start
        if start != end:
            yield end
        
        # 2. Initialize the queue with the primary range
        # We use a set to keep track of what we've already yielded
        queue = deque([(start, end)])
        seen = {start, end}
        
        while queue:

            low, high = queue.popleft()
            # Calculate the midpoint

            mid = (low + high) // 2
            # If the midpoint is a new unique integer, yield it

            if mid not in seen:
                yield mid
                seen.add(mid)

                # Queue the sub-ranges to keep bisecting
                # We add (low, mid) then (mid, high) to spread out the values
                queue.append((low, mid))
                queue.append((mid, high)) 



def printr(high,low,mode,log):

    for i in bisect_range(low,high,log):
        print(i,end=" " if mode == "list" else "\n")

    if mode == "list": 
        print()
    else:
        pass
    pass

# Usage:
#for value in bisect_range(1, 8):
#    print(value, end=" ")
# Output: 1 8 4 2 6 3 5 7


if __name__ == "__main__":


    import argparse    
    import sys
    parser = argparse.ArgumentParser(description="For printing rec bisect queue")

    # Define a positional argument
    parser.add_argument('high', type=int,help='The high end')
    parser.add_argument('low',type=int, default=0,help='The low end')
    parser.add_argument('--mode', choices=['stream', 'list'], default='stream',
                    help='Set the output mode (default: stream)')

    parser.add_argument('--log',action="store_true",
                    help='Log mode')


    parser.add_argument('--repeat','-r',type=int, default=1,help='how many times (max) should we repeat')
    args = parser.parse_args()
    
    for i in range(args.repeat):
        printr(args.low,args.high,args.mode,args.log)




