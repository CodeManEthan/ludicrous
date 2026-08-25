/* Name pool for client-side (v2) games.
 *
 * A mirror of random_names.py -- the v1 server path draws player names from
 * the Python copy, and a v2 game never talks to the server, so the browser
 * needs its own. Same 328 names, same order; keep the two in step.
 */
"use strict";

const NAME_POOL = [
  "Aaron", "Abby", "Adam", "Adrian", "Aiden", "Alan", "Alex", "Alexa", "Alice", "Allison",
  "Alyssa", "Amanda", "Amber", "Amy", "Andrea", "Andrew", "Angela", "Anna", "Anthony", "April",
  "Arthur", "Ashley", "Austin", "Autumn", "Ava", "Barbara", "Becky", "Ben", "Beth", "Betty",
  "Blake", "Bob", "Brad", "Brady", "Brandon", "Brenda", "Brian", "Brittany", "Brooke", "Bruce",
  "Bryan", "Caitlin", "Caleb", "Cameron", "Carl", "Carla", "Carmen", "Carol", "Caroline", "Carrie",
  "Catherine", "Cathy", "Chad", "Charles", "Charlie", "Chase", "Chelsea", "Cheryl", "Chris", "Christina",
  "Christine", "Christopher", "Cindy", "Claire", "Clara", "Claudia", "Clayton", "Cody", "Colin", "Colleen",
  "Connor", "Corey", "Courtney", "Craig", "Crystal", "Curtis", "Cynthia", "Daisy", "Dakota", "Dana",
  "Daniel", "Danielle", "David", "Dawn", "Dean", "Debbie", "Deborah", "Denise", "Derek", "Diana",
  "Diane", "Dominic", "Donna", "Dylan", "Eddie", "Edward", "Eleanor", "Elena", "Eli", "Elijah",
  "Elizabeth", "Ella", "Ellen", "Emily", "Emma", "Eric", "Erica", "Erik", "Erin", "Ethan",
  "Eva", "Evan", "Evelyn", "Faith", "Felix", "Fiona", "Francis", "Frank", "Gabriel", "Gavin",
  "George", "Georgia", "Gina", "Grace", "Greg", "Gregory", "Haley", "Hannah", "Harold", "Harry",
  "Heather", "Helen", "Holly", "Hope", "Hunter", "Ian", "Isaac", "Isabella", "Jack", "Jacob",
  "Jade", "Jake", "James", "Jamie", "Jane", "Jared", "Jason", "Jasmine", "Jean", "Jeff",
  "Jeffrey", "Jenna", "Jennifer", "Jeremy", "Jerry", "Jessica", "Jill", "Jimmy", "Joan", "Joanna",
  "Joe", "Joel", "John", "Johnny", "Jordan", "Joseph", "Josh", "Joshua", "Joy", "Joyce",
  "Julia", "Julian", "Julie", "Justin", "Kaitlyn", "Karen", "Karla", "Katherine", "Kathleen", "Katie",
  "Katrina", "Kayla", "Keith", "Kelly", "Kelsey", "Ken", "Kendra", "Kenneth", "Kevin", "Kim",
  "Kimberly", "Kristen", "Kristin", "Kyle", "Kylie", "Laura", "Lauren", "Lena", "Leo", "Leonard",
  "Liam", "Lillian", "Lindsay", "Lisa", "Logan", "Lori", "Louis", "Lucas", "Lucy", "Luke",
  "Mackenzie", "Madeline", "Madison", "Maggie", "Mallory", "Maria", "Mariah", "Marie", "Marilyn", "Mario",
  "Mark", "Martha", "Martin", "Mary", "Mason", "Matthew", "Megan", "Melanie", "Melissa", "Michael",
  "Michelle", "Miguel", "Molly", "Morgan", "Nancy", "Nathan", "Nathaniel", "Neil", "Nicholas", "Nicole",
  "Noah", "Nora", "Oliver", "Olivia", "Owen", "Paige", "Pamela", "Patricia", "Patrick", "Paul",
  "Paula", "Peter", "Philip", "Phoebe", "Rachel", "Ralph", "Randy", "Ray", "Rebecca", "Reese",
  "Regina", "Renee", "Richard", "Riley", "Robert", "Robin", "Roger", "Ronald", "Rose", "Ross",
  "Ryan", "Samantha", "Samuel", "Sandra", "Sara", "Sarah", "Scott", "Sean", "Sebastian", "Shane",
  "Shannon", "Sharon", "Sheila", "Shelby", "Sierra", "Sofia", "Sophia", "Spencer", "Stephanie", "Stephen",
  "Steve", "Steven", "Sue", "Summer", "Susan", "Sydney", "Tabitha", "Tammy", "Tara", "Taylor",
  "Teresa", "Terri", "Terry", "Thomas", "Tiffany", "Tim", "Timothy", "Todd", "Tony", "Tracy",
  "Travis", "Trevor", "Trinity", "Tyler", "Vanessa", "Victor", "Victoria", "Vincent", "Violet", "Virginia",
  "Wendy", "Will", "William", "Wyatt", "Xavier", "Zach", "Zachary", "Zoe"
];
