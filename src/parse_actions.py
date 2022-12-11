import pickle

# proginfo: ProgramInfo
# action: [str]
def do_action(proginfo, action):

    if action[0] == "pickle":
        outfile = open(action[1], 'wb')
        pickle.dump(proginfo, outfile, protocol=2)

    elif action[0] == "summary":
        proginfo.print_summary()

    else:
        print("Error: Invalid action '{}' provided as argument.".format(action[0]))
        exit(1)