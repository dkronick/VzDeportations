
********************************************************************************
* Save ICE arrests so as to identify *interior* removals
********************************************************************************

* arrests (to identify interior arrests)
import delimited "arrests-latest.csv", varnames(1) clear 
keep unique_identifier
duplicates drop /* This isn't QUITE right because a person could be arrested after a border deportation? But that'll be a tiny fraction */
rename unique_identifier anonymizedidentifier
gen inarrestsdata = 1
tempfile arrestees 
save `arrestees' 

********************************************************************************
* Load removals data
********************************************************************************

* removals: 2025 
import delimited "2026-ICLI-00005_Removals_FY25_20260311_Redacted.csv", ///
	   varnames(7) rowrange(7) clear 
tempfile file2025
save `file2025'	   
	   	   
* removals: 2026
import delimited "2026-ICLI-00005_Removals_FY26_20260311_Redacted.csv", ///
	   varnames(7) rowrange(7) clear 
	   
* add 2025
append using `file2025'
duplicates drop

********************************************************************************
* Merge ICE arrests so as to distinguish interior from border removals
********************************************************************************

* identify interior removals
drop if anonymizedidentifier == "" /* Following Blair and Hausman */
merge m:1 anonymizedidentifier using `arrestees'
drop if _m == 2 
drop _m 

* counts
gen totalremovals = 1 /* Will sum this later on */
rename inarrestsdata interiorremovals

********************************************************************************
* Collapse to day--Venezuela/Other level
********************************************************************************

* country of origin
gen country = "VENEZUELA" if citizenshipcountry == "VENEZUELA"
replace country = "ALL OTHERS" if country == ""

* date	   
gen int departed_d = date(substr(departeddate,1,10), "YMD")
format departed_d %td

* collapse to day
* NOTE: If the same person was deported twice, this counts both removals
collapse (sum) totalremovals interiorremovals, by(country departed_d)

* full panel 
egen countryid = group(country)
tsset countryid departed_d 
tsfill, full
foreach var of varlist *removals {
	replace `var' = 0 if `var' == .
	}
replace country = country[_n-1] if country == ""

********************************************************************************
* Calculate numbers reported in paragraph 2
********************************************************************************

* Comparing post-January 16 to all of the second half of 2025
qui su interiorremovals if (departed_d >= td(16jan2026) & departed_d <= td(10mar2026)) ///
		& country == "VENEZUELA", d
di `r(sum)'
local post (`r(sum)' / (td(10mar2026)-td(16jan2026)))
di `post'

qui su interiorremovals if (departed_d >= td(01jul2025) & departed_d <= td(31dec2025))  ///
		& country == "VENEZUELA", d
di `r(sum)'
local mean2025 (`r(sum)' / (td(31dec2025)-td(01jul2025)))
di `mean2025'

di `post' / `mean2025'


* Comparing post-January 16 to the second half of 2025 through Dec. 9 (flights paused Dec 10)
qui su interiorremovals if (departed_d >= td(16jan2026) & departed_d <= td(10mar2026)) ///
		& country == "VENEZUELA", d
di `r(sum)'
local post (`r(sum)' / (td(10mar2026)-td(16jan2026)))
di `post'

qui su interiorremovals if (departed_d >= td(01jul2025) & departed_d <= td(09dec2025))  ///
		& country == "VENEZUELA", d
di `r(sum)'
local mean2025 (`r(sum)' / (td(09dec2025)-td(01jul2025)))
di `mean2025'

di `post' / `mean2025'


* Highest three-week period
qui su interiorremovals if (departed_d >= td(16jan2026) & departed_d <= td(16jan2026)+20) ///
		& country == "VENEZUELA", d
di `r(sum)'
local post3weeks (`r(sum)')
di `post3weeks' / 21

sort country departed_d
by country: gen cum_ir = sum(interiorremovals)
by country: gen prev3weeks_ir = cum_ir - cum_ir[_n-21] 
su prev3weeks_ir if yofd(departed_d) == 2025 & country == "VENEZUELA"
local pre3weeks (`r(max)')
di `pre3weeks' / 21

di `post3weeks' / `pre3weeks'


********************************************************************************
* Figures 1 and 2
********************************************************************************

* collapse to week
gen week = wofd(departed_d)
format week %tw
collapse (sum) totalremovals interiorremovals, by(country week)

/* Figure 1: NOTE, this is similar but not identical to Claude
   because of how weeks are defined (see Python code) */
twoway bar interiorremovals week if country == "ALL OTHERS", ///
	xline(`=wofd(td(03jan2026))')

* Figure 2
twoway bar interiorremovals week if country == "VENEZUELA", ///
	xline(`=wofd(td(03jan2026))')



********************************************************************************
* End of do file
********************************************************************************
