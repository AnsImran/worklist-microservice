"""One-time script to generate 1000 patient names with unique MRNs."""
import json
import random

first_names = [
    "James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Elizabeth",
    "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Christopher","Karen",
    "Charles","Lisa","Daniel","Nancy","Matthew","Betty","Anthony","Margaret","Mark","Sandra",
    "Donald","Ashley","Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle",
    "Kenneth","Carol","Kevin","Amanda","Brian","Dorothy","George","Melissa","Timothy","Deborah",
    "Ronald","Stephanie","Edward","Rebecca","Jason","Sharon","Jeffrey","Laura","Ryan","Cynthia",
    "Jacob","Kathleen","Gary","Amy","Nicholas","Angela","Eric","Shirley","Jonathan","Anna",
    "Stephen","Brenda","Larry","Pamela","Justin","Emma","Scott","Nicole","Brandon","Helen",
    "Benjamin","Samantha","Samuel","Katherine","Raymond","Christine","Gregory","Debra","Frank","Rachel",
    "Alexander","Carolyn","Patrick","Janet","Jack","Catherine","Dennis","Maria","Jerry","Heather",
    "Tyler","Diane","Aaron","Ruth","Jose","Julie","Adam","Olivia","Nathan","Joyce",
    "Henry","Virginia","Douglas","Victoria","Peter","Kelly","Zachary","Lauren","Kyle","Christina",
    "Noah","Joan","Ethan","Evelyn","Jeremy","Judith","Walter","Megan","Christian","Andrea",
    "Keith","Cheryl","Roger","Hannah","Terry","Jacqueline","Austin","Martha","Sean","Gloria",
    "Gerald","Teresa","Carl","Ann","Harold","Sara","Dylan","Madison","Arthur","Frances",
    "Lawrence","Kathryn","Jordan","Janice","Jesse","Jean","Bryan","Abigail","Billy","Alice",
    "Bruce","Judy","Gabriel","Sophia","Joe","Grace","Logan","Denise","Albert","Amber",
    "Willie","Doris","Alan","Marilyn","Eugene","Danielle","Russell","Beverly","Vincent","Isabella",
    "Philip","Theresa","Bobby","Diana","Johnny","Natalie","Bradley","Brittany","Roy","Charlotte",
    "Elijah","Marie","Randy","Kayla","Wayne","Alexis","Howard","Lori","Carlos","Alyssa",
]

last_names = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
    "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
    "Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson",
    "Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
    "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell","Carter","Roberts",
    "Gomez","Phillips","Evans","Turner","Diaz","Parker","Cruz","Edwards","Collins","Reyes",
    "Stewart","Morris","Morales","Murphy","Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper",
    "Peterson","Bailey","Reed","Kelly","Howard","Ramos","Kim","Cox","Ward","Richardson",
    "Watson","Brooks","Chavez","Wood","James","Bennett","Gray","Mendoza","Ruiz","Hughes",
    "Price","Alvarez","Castillo","Sanders","Patel","Myers","Long","Ross","Foster","Jimenez",
    "Powell","Jenkins","Perry","Russell","Sullivan","Bell","Coleman","Butler","Henderson","Barnes",
    "Gonzales","Fisher","Vasquez","Simmons","Graham","Murray","Ford","Castro","Marshall","Owens",
    "Harrison","Fernandez","McDonald","Woods","Washington","Kennedy","Wells","Vargas","Henry","Chen",
    "Freeman","Webb","Tucker","Guzman","Burns","Crawford","Olson","Simpson","Porter","Hunter",
    "Gordon","Mendez","Silva","Shaw","Snyder","Mason","Dixon","Munoz","Hunt","Hicks",
    "Holmes","Palmer","Wagner","Black","Robertson","Boyd","Rose","Stone","Salazar","Fox",
    "Warren","Mills","Meyer","Rice","Schmidt","Garza","Daniels","Ferguson","Nichols","Stephens",
    "Soto","Weaver","Ryan","Gardner","Payne","Grant","Dunn","Kelley","Spencer","Hawkins",
    "Arnold","Pierce","Hansen","Peters","Santos","Hart","Bradley","Knight","Elliott","Riley",
    "Cunningham","Duncan","Armstrong","Hudson","Carroll","Lane","Andrews","Alvarado","Ray","Delgado",
]

middle_names = [
    "A","B","C","D","E","F","G","H","J","K","L","M","N","P","R","S","T","W",
    "Ann","Lee","Marie","James","Ray","Lynn","Jean","Mae","Jo","Kay",
    "Michael","David","Robert","Allen","Dean","Paul","Scott","Wayne","Earl","Dale",
]

random.seed(42)
patients = []
used_names = set()
mrn_counter = 2100000

for i in range(1000):
    while True:
        first = random.choice(first_names)
        last = random.choice(last_names)
        middle = random.choice(middle_names)
        full_name = f"{last}, {first} {middle}"
        if full_name not in used_names:
            used_names.add(full_name)
            break

    mrn = f"SHHD{mrn_counter + i}"
    dob_year = random.randint(1940, 2005)
    dob_month = random.randint(1, 12)
    dob_day = random.randint(1, 28)
    dob = f"{dob_month:02d}/{dob_day:02d}/{dob_year}"

    patients.append({"name": full_name, "mrn": mrn, "dob": dob})

output = {
    "_comment": "1000 pre-generated patients with unique MRNs. Same patient always has the same MRN across studies.",
    "patients": patients,
}

with open("data/pools/patients.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Generated {len(patients)} patients")
print(f"Sample: {patients[0]}")
print(f"Sample: {patients[999]}")
