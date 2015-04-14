import datetime

def is_even(n):
    return n % 2 == 0

class Define(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __str__(self):
        return "#define {} ({})\n".format(self.name.upper(), self.value)

    def __repr__(self):
        return self.__str__()


class Config(object):
    def __init__(self, baudrate, prescaler, clks_pr_bit, Tbit, Tsyns, Tprs, Tph1, Tph2, Tsjw, error_rate):
        self.baudrate = baudrate
        self.prescaler = prescaler
        self.clks_pr_bit = clks_pr_bit
        self.Tbit = Tbit
        self.Tsyns = Tsyns
        self.Tprs = Tprs # Propagation segment
        self.Tph1 = Tph1 # Phase segment 1
        self.Tph2 = Tph2 # Phase segment 2
        self.Tsjw = Tsjw
        self.error_rate = error_rate

    def __str__(self):
        return "baud: {} err: {}".format(self.baudrate, self.error_rate)

    def __repr__(self):
        return self.__str__()

    def header_defs(self):
        return [
            Define("CAN_BAUDRATE", self.baudrate),
            Define("CAN_PRESCALER", self.prescaler),
            Define("CAN_CLKS_PR_BIT", self.clks_pr_bit),
            Define("CAN_TBIT", self.Tbit),
            Define("CAN_TSYNS", self.Tsyns),
            Define("CAN_TPRS", self.Tprs),
            Define("CAN_TPH1", self.Tph1),
            Define("CAN_TPH2", self.Tph2),
            Define("CAN_SJW", self.Tsjw),
            Define("CAN_ERR_RATE", self.error_rate),
        ]

def get_config(baudrate, cpu_freq):
    valid_configs = []
    clks_pr_bit = cpu_freq / baudrate

    # Tbit must be in the range 8..25 inclusive
    for Tbit in range(8, 25 + 1):
        error_rate = clks_pr_bit % Tbit

        prescaler = int(clks_pr_bit / Tbit)

        # on the AVR the BRP register that holds the prescaler is a 6 bit value
        if prescaler > 2 ** 6: continue

        Tsyns = 1  # Tsyns is always 1 TQ
        Tprs = int(Tbit / 2 if is_even(Tbit) else (Tbit - 1) / 2) # Prop_Seg
        Tph1 = int(Tprs / 2 if is_even(Tbit - Tprs - Tsyns) else (Tprs / 2) + 1)
        Tph2 = int(Tprs / 2)
        Tsjw = 1 # can vary from 1 to 4 but is 1 in all avr examples

        # Check each value is within its valid ranges
        if (Tbit != Tsyns + Tprs + Tph1 + Tph2 or not (
                1 <= Tprs and Tprs <= 8) or not (
                1 <= Tph1 and Tph1 <= 8) or not (2 <= Tph2 and Tph2 <= Tph1)):
            continue

        min_err_rate = 0.5
        if Tprs == 1 and (Tph1 == 4 and Tph2 == 4 and Tsjw == 4) and baudrate > 125*1000:
            min_err_rate = 1.58

        if error_rate < min_err_rate:
            valid_configs.append(
                Config(baudrate, prescaler, clks_pr_bit, Tbit, Tsyns, Tprs, Tph1, Tph2, Tsjw, error_rate))

    return valid_configs

def best_error_rate(baudrate, cpu_freq):
    confs = get_config(baudrate, cpu_freq)
    if confs == []:
        return None
    else:
        # sort by error_rate and pick first element
        return sorted(confs, key=lambda config: config.error_rate)[0]


def make_header(baud, cpu_freq, name):
    name = name.upper().replace(" ", "_")
    header_start = "\n".join([
        "/**",
        " * " + datetime.datetime.now().strftime('%c'),
        " * This file is machine generated and should not be altered by hand.",
        " */",
        "\n",
        "#ifndef {}_H".format(name),
        "#define {}_H".format(name),
        "\n"
    ])

    encaps_start = "#if F_CPU == {}\n\n".format(cpu_freq)

    conf = best_error_rate(baud, cpu_freq)

    conf_defs = "".join(map(str, conf.header_defs()))

    reg_vals ="".join(map(str, [
        Define("CANBT1_VALUE", "(CAN_PRESCALER-1)<<BRP0"),
        Define("CANBT2_VALUE", "((CAN_TPRS-1)<<PRS0) | ((CAN_SJW-1)<<SJW0)"),
        Define("CANBt3_VALUE", "((CAN_TPH1-1)<<PHS10) | ((CAN_TPH2-1)<<PHS20)"),
    ]))

    encaps_end = "\n#endif /* {} */\n".format(encaps_start[:-3])

    header_end = "\n".join([
        "\n"
        "#endif /* {}_H */".format(name),
    ])

    return header_start + encaps_start + conf_defs + reg_vals + encaps_end + header_end


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--f_cpu", dest="f_cpu", help="Clock frequency of the system clock in hz", metavar="f_cpu", type=int, required=True)
    parser.add_argument("--baudrate", dest="baudrate", help="The desired CAN baudrate", metavar="baudrate", type=int, required=True)

    args = parser.parse_args()

    print(make_header(args.baudrate, args.f_cpu, "can_baud"))


if __name__ == "__main__":
    main()
