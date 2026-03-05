# Jot-two
A rebuild of '[Jot](https://github.com/Kalekdan/jot)' designed to be more scaleable, and built with some of the learnings from the first Jot.

Implements many of the same functionalities of Jot. Primary enhancements include:
- Tools becoming more modular
  - Should be able to add tools without needing to change any of the code, just drop in a new module
- Less sequential
  - Jot was very sequential in it's processing, would wait for one thing to happen before the next would start. Needs to be able to support multiple activities running in parallel, and make use of streaming where possible
- More inputs
  - Jot only allowed voice input, but I would like to be able to interface with Jot from anywhere


### High Level Design
<img width="1599" height="1281" alt="image" src="https://github.com/user-attachments/assets/21e059e4-76bd-4aa8-9764-0478630673ba" />
