#!/usr/bin/env python3

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
    def __init__(self, cpu_freq, baudrate, prescaler, clks_pr_bit, Tbit, Tsyns, Tprs, Tph1, Tph2, Tsjw, error_rate):
        self.cpu_freq = cpu_freq
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
        return "CAN baudrate: {} cpu frequency: {}".format(self.baudrate, self.cpu_freq)

    def __repr__(self):
        return self.__str__()

    def header_defs(self):
        return [
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

    def create_header(self):
        encaps_start = "#if CAN_BAUDRATE == {}\n\n".format(self.baudrate)

        defines = "".join(map(str, self.header_defs()))

        reg_vals ="".join(map(str, [
            Define("CANBT1_VALUE", "(CAN_PRESCALER-1)<<BRP0"),
            Define("CANBT2_VALUE", "((CAN_TPRS-1)<<PRS0) | ((CAN_SJW-1)<<SJW0)"),
            Define("CANBt3_VALUE", "((CAN_TPH1-1)<<PHS10) | ((CAN_TPH2-1)<<PHS20)"),
        ]))

        encaps_end = "\n#endif /* CAN_BAUDRATE {}*/\n".format(self.baudrate)

        return encaps_start + defines + reg_vals + encaps_end + "\n"

def wrap_header(contents, file_name):
    file_name = file_name.upper().replace(" ", "_")
    header_start = "\n".join([
            "/**",
            " * " + datetime.datetime.now().strftime('%c'),
            " * This file is machine generated and should not be altered by hand.",
            " */",
            "\n",
            "#ifndef {}_H".format(file_name),
            "#define {}_H".format(file_name),
            "\n",
            ""
    ])

    header_end = "\n".join([
            "\n"
            "#endif /* {}_H */".format(file_name),
    ])

    return header_start + contents + header_end


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
                Config(cpu_freq, baudrate, prescaler, clks_pr_bit, Tbit, Tsyns, Tprs, Tph1, Tph2, Tsjw, error_rate))

    return valid_configs

def best_error_rate(baudrate, cpu_freq):
    confs = get_config(baudrate, cpu_freq)
    if confs == []:
        return None
    else:
        # sort by error_rate and pick first element
        return sorted(confs, key=lambda config: config.error_rate)[0]


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--f_cpu", dest="f_cpu", help="Clock frequency of the system clock in hz", type=int, default=8000000)
    parser.add_argument("--baudrate", dest="baudrates", help="One or more desired CAN baudrates", type=int, required=True , nargs='*')
    parser.add_argument("--config", dest="config", help="Print the configuration", action='store_true', default=False)
    parser.add_argument("--header", dest="header", help="Generate a C header file with suitable configurations for the baudrate at the given cpu frequency", default=False, action='store_true')

    args = parser.parse_args()
    confs = [best_error_rate(baudrate, args.f_cpu) for baudrate in args.baudrates]

    if confs == []:
        print("No valid baudrate config found")
        exit(1)

    zipped = zip(args.baudrates, confs)

    if args.header:
        header = ""
        for conf in zipped:
            if conf[1] is None:
                header += "\n".join([
                    "#if CAN_BAUDRATE == {}".format(conf[0]),
                    "#error No valid config found for {} bps CAN baudrate".format(conf[0]),
                    "#endif /* CAN_BAUDRATE == {} */".format(conf[0]),
                ]) + "\n"
                continue
            conf = conf[1]
            header += conf.create_header()
        print(wrap_header(header, "can_baud"))
    else:
        for conf in zipped:
            if conf[1] is None:
                print("No valid config found for {} bps baudrate".format(conf[0]))
                continue
            conf = conf[1]
            print("CPU frequency {} hz, CAN baudrate {} bps, error rate: {}%".format(conf.cpu_freq, conf.baudrate, conf.error_rate))
            if args.config:
                print("\n\t".join([
                    "Config at Time Quantum = 1",
                    "Prescaler: {}".format(conf.prescaler),
                    "Tbit: {}".format(conf.Tbit),
                    "Sync: {}".format(conf.Tsyns),
                    "Propagation segment: {}".format(conf.Tprs),
                    "Phase Segment 1: {}".format(conf.Tph1),
                    "Phase Segment 2: {}".format(conf.Tph2),
                    "SJW: {}".format(conf.Tsjw),
                ]))


if __name__ == "__main__":
    main()
