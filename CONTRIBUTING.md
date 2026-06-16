## Contributing

Hi there! We're thrilled that you'd like to contribute to this project. Your help is essential for keeping this project great. This structure is based on the template from github/microsoft/terminal project.

Contributions to this project are released to the public under the project's open source license ([SoftwareDevLabs License](https://github.com/SoftwareDevLabs/.github/blob/main/LICENSE.md).

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## Open Development Workflow

When the team finds **issues** we file them in the repo. When we propose new ideas or think-up new features, we file new **feature requests**. When we work on fixes or features, we create branches and work on those improvements. And when PRs are reviewed, we review in public - including all the good, the bad, and the ugly parts.

The point of doing all this work in public is to ensure that we are holding ourselves to a high degree of transparency, and so that the community sees that we apply the same processes and hold ourselves to the same quality-bar as we do to community-submitted issues and PRs.

### Repo Bot (currently under construction)

The team triages new issues several times a week. During triage, the team uses labels to categorize, manage, and drive the project workflow.

We employ [a bot engine](./doc/bot.md) to help us automate common processes within our workflow.

We drive the bot by tagging issues with specific labels which cause the bot engine to close issues, merge branches, etc. This bot engine helps us keep the repo clean by automating the process of notifying appropriate parties if/when information/follow-up is needed, and closing stale issues/PRs after reminders have remained unanswered for several days.

Therefore, if you do file issues, or create PRs, please keep an eye on your GitHub notifications. If you do not respond to requests for information, your issues/PRs may be closed automatically.


## Before you start, file an issue

Please follow this simple rule to help us eliminate any unnecessary wasted effort & frustration, and ensure an efficient and effective use of everyone's time - yours, ours, and other community members':

> 👉 If you have a question, think you've discovered an issue, would like to propose a new feature, etc., then find/file an issue **BEFORE** starting work to fix/implement it.

### Search existing issues first

Before filing a new issue, search existing open and closed issues first: This project is moving fast! It is likely someone else has found the problem you're seeing, and someone may be working on or have already contributed a fix!

If no existing item describes your issue/feature, great - please file a new issue:

### File a new Issue

* Don't know whether you're reporting an issue or requesting a feature? File an **issue**
* Have a question that you don't see answered in docs, videos, etc.? File an **issue**
* Want to know if we're planning on building a particular feature? File an **issue**
* Got a great idea for a new feature? File an **issue**/**request**/**idea**
* Don't understand how to do something? File an **issue**
* Found an existing issue that describes yours? Great - upvote and add additional commentary / info / repro-steps / etc.

When you hit "New **Issue**", select the type of issue closest to what you want to report/ask/request:
![New issue types](/doc/images/new-issue-template.png)

### Complete the template

**Complete the information requested in the issue template, providing as much information as possible**. The more information you provide, the more likely your issue/ask will be understood and implemented. Helpful information includes:

### DO NOT post "+1" comments

> ⚠ DO NOT post "+1", "me too", or similar comments - they just add noise to an issue.

If you don't have any additional info/context to add but would like to indicate that you're affected by the issue, upvote the original issue by clicking its [+😊] button and hitting 👍 (+1) icon. This way we can actually measure how impactful an issue is.

---

## Contributing fixes / features

If you're able & willing to help fix issues and/or implement features, we'd love your contribution!

The list of ["good first issue"](https://github.com/SoftwareDevLabs/SDLC_core/issues?q=is%3Aopen+is%3Aissue+label%3A%22Help+Wanted%22++label%3A%22good+first+issue%22+)s is another set of issues that might be easier for first-time contributors. Once you're feeling more comfortable in the codebase, feel free to just use the ["Help Wanted"](https://github.com/SoftwareDevLabs/SDLC_core/issues?q=is%3Aopen+is%3Aissue+label%3A%22Help+Wanted%22+) label, or just find any issue you're interested in and hop in!

Generally, we categorize issues in the following way:
* ["Bugs"](https://github.com/SoftwareDevLabs/SDLC_core/issues?q=is%3Aopen+is%3Aissue+label%3A%22Issue-Bug%22+) are parts of the software module that are not quite working the right way. There's code to already support some scenario, but it's not quite working right. Fixing these is generally a matter of debugging the broken functionality and fixing the wrong code.
* ["Tasks"](https://github.com/SoftwareDevLabs/SDLC_core/issues?q=is%3Aopen+is%3Aissue+label%3A%22Issue-Task%22+) are usually new pieces of functionality that aren't yet implemented for the software module. These are usually smaller features, which we believe
  - could be a single, atomic PR
  - Don't require much design consideration, or we've already written the spec for the larger feature they belong to.
* ["Features"](https://github.com/SoftwareDevLabs/SDLC_core/issues?q=is%3Aopen+is%3Aissue+label%3A%22Issue-Feature%22+) are larger pieces of new functionality. These are usually things we believe would require larger discussion of how they should be implemented, or they'll require some complicated new settings. They might just be features that are composed of many individual tasks. Often times, with features, we like to have a spec written before development work is started, to make sure we're all on the same page (see below).

Bugs and tasks are obviously the easiest to get started with, but don't feel afraid of features either! We've had some community members contribute some amazing "feature"-level work to our repos (albeit, with lots of discussion 😄).


Often, we like to assign issues that generally belong to somebody's area of expertise to the team member that owns that area. This doesn't mean the community can't jump in -- they should reach out and have a chat with the assignee to see if it'd okay to take. If an issue's been assigned more than a month ago, there's a good chance it's fair game to try yourself.

### To Spec or not to Spec

Some issues/features may be quick and simple to describe and understand. For such scenarios, once a team member has agreed with your approach, skip ahead to the section headed "Fork, Branch, and Create your PR", below.

Small issues that do not require a spec will be labelled `Issue-Bug` or `Issue-Task`.

However, some issues/features will require careful thought & formal design before implementation. For these scenarios, we'll request that a spec is written and the associated issue will be labeled `Issue-Feature`. More often than not, we'll add such features to the ["Specification Tracker" project](https://github.com/orgs/SoftwareDevLabs/projects/9/views/1).

Specs help collaborators discuss different approaches to solve a problem, describe how the feature will behave, how the feature will impact the user, what happens if something goes wrong, etc. Driving towards agreement in a spec, before any code is written, often results in simpler code, and less wasted effort in the long run.

Specs will be managed in a very similar manner as code contributions so please follow the "[Fork, Branch and Create your PR](CONTRIBUTING.md#fork-clone-branch-and-create-your-pr)" section below.

### Writing / Contributing-to a Spec

To write/contribute to a spec: fork, branch and commit via PRs, as you would with any code changes.

Specs are written in markdown, stored under the [`\doc\specs`](./doc/specs) folder and named `[issue id] - [spec description].md`.

👉 **It is important to follow the spec templates and complete the requested information**. The available spec templates will help ensure that specs contain the minimum information & decisions necessary to permit development to begin. In particular, specs require you to confirm that you've already discussed the issue/idea with the team in an issue and that you provide the issue ID for reference.

Team members will be happy to help review specs and guide them to completion.

### Help Wanted

Once the team has approved an issue/spec, development can proceed. If no developers are immediately available, the spec can be parked ready for a developer to get started. Parked specs' issues will be labeled "Help Wanted". To find a list of development opportunities waiting for developer involvement, visit the Issues and filter on [the Help-Wanted label](https://github.com/SoftwareDevLabs/SDLC_core/labels/Help%20Wanted).

---

# Development

### Fork, Clone, Branch and Create your PR

Once you've discussed your proposed feature/fix/etc. with a team member, and you've agreed an approach or a spec has been written and approved, it's time to start development:

1. Fork the repo if you haven't already
1. Clone your fork locally
1. Create & push a feature branch: `git checkout -b my-branch-name` 
1. Create a [Draft Pull Request (PR)](https://github.blog/2019-02-14-introducing-draft-pull-requests/)
1. Work on your changes, add tests and make sure the tests still pass
1. Build and see if it works. Consult [How to build](./doc/building.md) if you have problems.
1. Push to your fork and submit a pull request
1. Pat yourself on the back and wait for your pull request to be reviewed and merged.

Here are a few things you can do that will increase the likelihood of your pull request being accepted:

- Follow standards for style and code quality
- Write tests.
- Keep your change as focused as possible. If there are multiple changes you would like to make that are not dependent upon each other, consider submitting them as separate pull requests.
- Write a [good commit message](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html).


### Testing

Testing is a key component in the development workflow. This software moduke should use well defined testing methodology to ensure that software modules and its key components are tested.

<!---TAEF (the Test Authoring and Execution Framework) as the main framework for testing.

If your changes affect existing test cases, or you're working on brand new features and also the accompanying test cases, see [TAEF](./doc/TAEF.md) for more information about how to validate your work locally.-->

### Code Review

When you'd like the team to take a look, (even if the work is not yet fully-complete), mark the PR as 'Ready For Review' so that the team can review your work and provide comments, suggestions, and request changes. It may take several cycles, but the end result will be solid, testable, conformant code that is safe for us to merge.

### Merge

Once your code has been reviewed and approved by the requisite number of team members, it will be merged into the main branch. Once merged, your PR will be automatically closed.


## Thank you

Thank you in advance for your contribution!

## Resources

- Our [developer documentation](https://developers.softwaredevlabs.com/)
- [How to Contribute to Open Source](https://opensource.guide/how-to-contribute/)
- [How to get faster PR reviews](https://github.com/kubernetes/community/blob/master/contributors/guide/pull-requests.md#best-practices-for-faster-reviews) by Kubernetes (but skip step 0)
- [Using Pull Requests](https://help.github.com/articles/about-pull-requests/)
- [GitHub Help](https://help.github.com)