#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright 2014,2015 Igalia S.L.
#  Carlos Alberto Lopez Perez <clopez@igalia.com>
#  Marcos Chavarría Teiejeiro <chavarria1991@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
      
import os
import urllib
import re
import requests
import json
import sys
import subprocess

RESULTS_URL_PREFIX = "https://build.webkit.org/results/"

class WKTestHunter:
    """ """
    def __init__(self, resultsdir, bot, alreadytriedfilename=".cache_already_tried", log=True):
        self.resultsdir = resultsdir
        self.bot = bot
        self.alreadytriedfilename = alreadytriedfilename
        self.log = log

    def __get_json_from_file (self, json_file_name):
        with open(json_file_name, "r") as json_file:
            json_data = json_file.read()
        # Clean it
        json_data = json_data.split('ADD_RESULTS(')[1]
        json_data = json_data.split(');')[0]
        try:
            return json.loads(json_data)
        except:
            raise ValueError("Exception caused by file: %s " % (json_file))

    def __download_result(self, revisionnum, buildnum):
        alreadytriedfile = os.path.join(self.resultsdir, self.bot, self.alreadytriedfilename)
        filepath = os.path.join(self.resultsdir, self.bot, "full_results_r%i_b%i.json" % (revisionnum, buildnum))
        downloadurl = "%s/r%i (%i)/full_results.json" % (self.bot, revisionnum, buildnum)
        downloadurl = RESULTS_URL_PREFIX + urllib.parse.quote(downloadurl)
        tries = 1
        req = requests.get(downloadurl)
        while req.status_code != requests.codes.ok and tries < 3:
             req = requests.get(downloadurl)
             tries = tries + 1
        if req.status_code == requests.codes.ok:
            with open(filepath, "w") as f:
                f.write(req.text)
        elif req.status_code == requests.codes.not_found:
            with open(alreadytriedfile, "a") as f:
                f.write("r%i_b%i\n" % (revisionnum, buildnum))

    def fetch_results(self):
        """Updates the results database."""

        botdir=os.path.join(self.resultsdir, self.bot)
        if not os.path.exists(botdir):
            os.makedirs(botdir)

        alreadytriedfile = os.path.join(botdir, self.alreadytriedfilename)
        if os.path.exists(alreadytriedfile):
            with open(alreadytriedfile, "r") as f:
                already_tried_text = f.read()
            already_tried_revisions = set([(int(a),int(b)) for a,b in re.findall("([0-9]+)_b([0-9]+)", already_tried_text)])
        else:
            open(alreadytriedfile, 'a').close()
            already_tried_revisions = set()
    
        if self.log: print("Fetching existent revisions...")
        results_url = RESULTS_URL_PREFIX + urllib.parse.quote(self.bot)
        results_web_text = requests.get(results_url).text
        existent_revisions = set([(int(a),int(b)) for a,b in  re.findall("r([0-9]+) \(([0-9]+)\)",results_web_text)])

        if self.log: print("Fetching have revisions...")
        file_regexp = re.compile("full_results_r([0-9]+)_b([0-9]+).json")
        have_revisions = set([(int(file_regexp.findall(f)[0][0]), int(file_regexp.findall(f)[0][1])) for f in os.listdir(botdir) if f.startswith("full")])

        if self.log: print("Calculate revisions to download...")
        download_revisions = sorted(list(existent_revisions - have_revisions - already_tried_revisions), key=lambda a:a[1])
        num_revs = len(download_revisions)

        if not num_revs and self.log: print("There aren't revisions to fetch!")

        for i,(revisionnum, buildnum) in enumerate(download_revisions):
            if self.log:
                prog = int((float(i+1)/num_revs) * 30)
                sys.stdout.write("\r[%s] (%2i/%2i) Downloading b%i - r%i." % (("#" * prog).ljust(30), i+1, num_revs, buildnum, revisionnum))
            self.__download_result(revisionnum, buildnum)
        if self.log: print("")

    def get_last_revision(self):
        """ Returns newest revision and build number. """
        pathresults = os.path.join(self.resultsdir, self.bot)
        results = os.listdir(pathresults)
        results = [r for r in results if r.startswith("full")]
        results.sort()
        rev,build = re.match("full_results_r([0-9]+)_b([0-9]+).json", results[-1]).groups()  
        return int(rev), int(build)     

    def __check_tests (self, d, prefix=""):
        reported_tests = {}
        for t in d:
            if type(d[t]) != dict:
                continue
            if "actual" not in d[t]:
                tests = self.__check_tests(d[t], "%s/%s" % (prefix, t))
                reported_tests.update(tests)
                continue
            if d[t]["actual"] == "PASS" and "PASS" not in d[t]["expected"].split(" "):
                d[t]["report"] = "NOWPASSING"
            if "report" in d[t]:
                reported_tests["%s/%s" % (prefix, t)] = d[t]
        return reported_tests

    def __get_failing_tests_for_build (self, build):
        """Gets the reported failing test from the specified build. If any build is
           specified, the last fetched build is used."""
        pathresults = os.path.join(self.resultsdir, self.bot)
        results = [r for r in os.listdir(pathresults) if r.find("b%i" % (build)) != -1]
        if not results:
            return []
        res_file = results[0]
          
        json_parsed = self.__get_json_from_file(os.path.join(pathresults, res_file))
        return self.__check_tests(json_parsed[u"tests"])
        
    def get_failing_tests (self, num_builds):
        """Gets the reported failing test from the specified build. If any build is
           specified, the last fetched build is used."""
        rev, build = self.get_last_revision()
        results_for_builds = []

        for b in range(build - num_builds + 1, build + 1):
            res = self.__get_failing_tests_for_build(b)
            results_for_builds.append(res)

        return_dict = results_for_builds.pop()
        while results_for_builds:
            curr_result = results_for_builds.pop()
            for test in curr_result:
                if test not in return_dict:
                   return_dict[test] = curr_result[test]
                   break
                if curr_result[test] == return_dict[test]:
                    break
                #If the expected value has changes the error that is valid is the last.
                if curr_result[test]["actual"]   != return_dict[test]["actual"] and \
                   curr_result[test]["expected"] == return_dict[test]["expected"]:
                    return_dict[test]["actual"] = " ".join(set(return_dict[test]["actual"].split(" ") + curr_result[test]["actual"].split(" ")))
                    return_dict[test]["report"] = "FLAKY"
        return return_dict
        
    def __get_test_result_for_file(self, result_file, test):
        try:
            revision, buildnumber = re.match("full_results_r([0-9]+)_b([0-9]+)\.json", result_file).groups()
            revision, buildnumber = int(revision), int(buildnumber)
        except:
            raise ValueError("Invalid file name")

        # Read file
        json_parsed = self.__get_json_from_file(os.path.join(self.resultsdir, self.bot, result_file))

        # Sanity check
        if int(json_parsed[u'revision']) != revision :
            if self.log: print("WARNING: Parsed revision %s don't match expected one %d for file %s" % (json_parsed['revision'], revision, jsonresult))
            revision = int(json_parsed[u'revision'])

        testparts=test.split('/')
        keytest=json_parsed[u'tests']

        try:
            for testpart in testparts:
                keytest=keytest[testpart]
            if keytest["actual"] == "PASS" and "PASS" not in keytest["expected"].split(" "):
                keytest["report"] = "NOWPASSING"
            return revision,keytest
        except KeyError: # This test didn't failed (or wasn't ran) on this rev.
            # If the whole set of tests didn't finished, mark it as unknown.
            result = "UNKNOWN" if json_parsed["interrupted"] else "NOERROR"
            return revision, {"actual": result}

    def get_test_results(self, test, first_rev=1):
        """Gets the available results for a test."""
        pathresults = os.path.join(self.resultsdir, self.bot)

        # The first comprehension condition is needed since if x is not a results file
        #  next condition will cause an exception breaking the whole comprehension.
        results_files = [x for x in os.listdir(pathresults) if x.startswith("full_results") and \
                         int(re.match("full_results_r([0-9]+)_b[0-9]+\.json", x).groups()[0]) >= first_rev]
        ret = {}
        num_files = len(results_files)

        if not results_files:
            raise ValueError("There aren't any valid result file to check. You provably need to update.")

        for i,f in enumerate(results_files):
            if self.log:
                prog = int((float(i+1)/num_files) * 30)
                sys.stdout.write("\r[%s] (%i/%i) Get results from %s" % (("#" * prog).ljust(30), i+1, num_files, f))
            rev,res = self.__get_test_result_for_file(f, test)
            if res["actual"] != "UNKNOWN":
                ret[rev] = res
        if self.log: print("")
        return ret

    def compress_results(self, results, merge_unknown=False):
        """ Compress the results dictionary joining two of more consecutive
            results with the same values."""
        revs = sorted(results.keys(), reverse=True)

        c_rev = revs.pop(0)
        ret = [{"start_ind": c_rev, "end_ind": c_rev, "res": results[c_rev]}]       

        while revs:
            c_rev = revs.pop(0)
            if ret[-1]["res"] != results[c_rev]:
                ret.append({"start_ind": c_rev, "end_ind": c_rev, "res":results[c_rev]})      
            elif merge_unknown or ret[-1]["start_ind"] - c_rev == 1:
                ret[-1]["start_ind"] = c_rev
            else:
                ret.append({"start_ind": c_rev, "end_ind": c_rev, "res":results[c_rev]})

        return ret

    def fill_gaps(self, results):
        """Fill the gaps between consecutive results if they don't have
            consecutive revision numbers."""
        sorted_results = sorted(results, key= lambda a: a["start_ind"])
    
        ret = [sorted_results.pop(0)]
 
        while sorted_results:
            c_res = sorted_results.pop(0)
            if c_res["start_ind"] - ret[-1]["end_ind"] > 1:
                if ret[-1]["res"]["actual"] == "UNKNOWN":
                    c_res["start_ind"] = ret[-1]["end_ind"] + 1            
                else:
                    ret.append(
                        {"start_ind":ret[-1]["end_ind"] + 1,
                         "end_ind": c_res["start_ind"] -1,
                         "res":{"actual":"UNKNOWN"}
                        })
            ret.append(c_res)
        return ret
